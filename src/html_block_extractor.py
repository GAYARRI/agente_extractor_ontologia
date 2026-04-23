from __future__ import annotations

import re
from bs4 import BeautifulSoup


class HTMLBlockExtractor:
    """
    Extractor de bloques HTML más permisivo para páginas de turismo,
    pero con filtros específicos para cortar bloques de cabecera,
    contacto, menús globales y contenido site-wide.
    """

    def __init__(self, min_text_length: int = 12):
        self.min_text_length = max(1, int(min_text_length))

        self.noise_keywords = [
            "menu", "nav", "header", "footer",
            "sidebar", "cookie", "banner",
            "login", "form", "search",
            "newsletter", "breadcrumbs", "breadcrumb",
            "pagination", "pager", "filter", "filters",
            "modal", "popup", "share", "social",
        ]

        self.ui_noise_fragments = [
            "phone number",
            "email",
            "login",
            "register",
            "password",
            "cookies",
            "política de cookies",
            "politica de cookies",
            "aviso legal",
            "privacy policy",
            "política de privacidad",
            "politica de privacidad",
        ]

        self.contact_keywords = [
            "teléfono", "telefono", "phone", "móvil", "movil",
            "email", "correo", "@",
            "facebook", "instagram", "x-twitter", "twitter", "linkedin",
            "oficinaturismo", "oficina de turismo",
            "plaza consistorial", "consistorial",
            "s/n", "cp ", "c.p.", "31001",
        ]

        self.portal_menu_keywords = [
            "descubre pamplona",
            "barrio a barrio",
            "verde y sostenible",
            "san fermín", "san fermin",
            "pelota vasca",
            "cultura muy viva",
            "camino de santiago",
            "gastronomía", "gastronomia",
            "turismo de salud",
            "qué ver", "que ver",
            "qué hacer", "que hacer",
            "planifica tu viaje",
            "dónde alojarse", "donde alojarse",
            "dónde comer", "donde comer",
            "cómo llegar", "como llegar",
            "moverse por pamplona",
            "donde aparcar",
            "consignas",
            "mapas y guías", "mapas y guias",
            "convention bureau",
            "área profesional", "area profesional",
            "facebook instagram", "instagram x-twitter",
        ]

        self.footer_signature_fragments = [
            "ayuntamiento de pamplona 31001",
            "ayuntamiento de pamplona",
            "descubre pamplona",
            "barrio a barrio",
            "moverse por pamplona",
            "mapas y guias",
            "mapas y guÇðas",
            "convention bureau",
            "area profesional",
            "Ç­rea profesional",
        ]

        self.short_ui = {
            "ver más", "ver mas", "leer más", "leer mas",
            "más info", "mas info", "contacto", "inicio",
            "mapa", "cómo llegar", "como llegar", "llamar",
            "reservar", "comprar", "cerrar",
        }

    # ==================================================
    # FILTRO DE TAGS BASURA
    # ==================================================

    def remove_noise(self, soup):
        for tag in soup([
            "script", "style", "nav", "header", "footer",
            "aside", "form", "noscript", "svg", "iframe",
        ]):
            tag.decompose()

        return soup

    # ==================================================
    # HELPERS
    # ==================================================

    def _normalize_text(self, text: str) -> str:
        text = str(text or "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _count_matches(self, low: str, patterns) -> int:
        return sum(1 for p in patterns if p in low)

    def _has_phone(self, text: str) -> bool:
        # patrones amplios para teléfonos europeos
        return bool(re.search(r"(?:\+?\d[\d\s\-]{7,}\d)", text))

    def _has_email(self, text: str) -> bool:
        return "@" in text and bool(re.search(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", text))

    def _is_contact_or_office_block(self, text: str) -> bool:
        low = text.lower()
        keyword_hits = self._count_matches(low, self.contact_keywords)

        if keyword_hits >= 2:
            return True

        if self._has_phone(text) and self._has_email(text):
            return True

        if self._has_phone(text) and keyword_hits >= 1:
            return True

        return False

    def _is_sitewide_menu_block(self, text: str) -> bool:
        low = text.lower()
        menu_hits = self._count_matches(low, self.portal_menu_keywords)

        # combinación muy típica del bloque que está contaminando
        if menu_hits >= 4:
            return True

        # menú + contacto/redes en el mismo bloque => casi seguro cabecera/sitewide
        if menu_hits >= 2 and self._is_contact_or_office_block(text):
            return True

        return False

    def _strip_footer_signature(self, text: str) -> str:
        normalized = self._normalize_text(text)
        low = normalized.lower()
        cut_points = []

        for marker in [
            "ayuntamiento de pamplona 31001",
            "descubre pamplona",
            "© 2025 ayuntamiento de pamplona",
        ]:
            idx = low.find(marker)
            if idx > 0:
                cut_points.append(idx)

        if cut_points:
            normalized = normalized[: min(cut_points)].strip()

        return normalized

    def _has_footer_signature(self, text: str) -> bool:
        low = self._normalize_text(text).lower()
        hits = self._count_matches(low, self.footer_signature_fragments)
        return hits >= 2

    def _is_mostly_ui_text(self, text: str) -> bool:
        low = text.lower()

        if any(fragment in low for fragment in self.ui_noise_fragments):
            return True

        if low in self.short_ui:
            return True

        return False

    # ==================================================
    # FILTRO DE CLASES / IDS HTML
    # ==================================================

    def is_noise_block(self, element):
        if not element:
            return True

        classes = " ".join(element.get("class", [])).lower()
        el_id = str(element.get("id", "")).lower()
        attrs = f"{classes} {el_id}".strip()

        if any(k in attrs for k in self.noise_keywords):
            return True

        text = self._normalize_text(element.get_text(" ", strip=True))
        if not text:
            return True

        if self._is_contact_or_office_block(text):
            return True

        if self._is_sitewide_menu_block(text):
            return True

        if self._has_footer_signature(text):
            return True

        return False

    # ==================================================
    # BLOQUES DE CONTENIDO
    # ==================================================

    def extract(self, html):
        soup = BeautifulSoup(html or "", "html.parser")
        soup = self.remove_noise(soup)

        blocks = []
        seen = set()

        candidates = soup.find_all([
            "section", "article", "div", "p",
            "li", "a", "h1", "h2", "h3", "h4",
            "span", "figcaption",
        ])

        for el in candidates:
            if self.is_noise_block(el):
                continue

            text = self._normalize_text(el.get_text(" ", strip=True))
            text = self._strip_footer_signature(text)

            if not text:
                continue

            if len(text) < self.min_text_length:
                continue

            if self._is_mostly_ui_text(text):
                continue

            # Evitar bloques absurdamente largos de página completa
            if len(text) > 5000:
                continue

            # segunda pasada defensiva sobre el propio texto
            if self._is_contact_or_office_block(text):
                continue

            if self._is_sitewide_menu_block(text):
                continue

            norm_key = text.lower()
            if norm_key in seen:
                continue
            seen.add(norm_key)

            nearest_heading = ""
            try:
                prev_heading = el.find_previous(["h1", "h2", "h3", "h4"])
                if prev_heading:
                    nearest_heading = self._normalize_text(prev_heading.get_text(" ", strip=True))
                    nearest_heading = self._strip_footer_signature(nearest_heading)
            except Exception:
                nearest_heading = ""

            parent = getattr(el, "parent", None)
            parent_tag = getattr(parent, "name", "") if parent else ""
            parent_class = ""
            parent_id = ""
            if parent:
                try:
                    parent_class = " ".join(parent.get("class", []))
                except Exception:
                    parent_class = ""
                try:
                    parent_id = parent.get("id")
                except Exception:
                    parent_id = ""

            anchor = el if el.name == "a" else el.find("a")
            link_text = ""
            link_href = ""
            if anchor:
                try:
                    link_text = self._normalize_text(anchor.get_text(" ", strip=True))
                    link_text = self._strip_footer_signature(link_text)
                except Exception:
                    link_text = ""
                try:
                    link_href = anchor.get("href")
                except Exception:
                    link_href = ""

            blocks.append({
                "text": text,
                "tag": el.name,
                "href": el.get("href"),
                "class": " ".join(el.get("class", [])),
                "id": el.get("id"),
                "heading": nearest_heading,
                "parent_tag": parent_tag,
                "parent_class": parent_class,
                "parent_id": parent_id,
                "link_text": link_text,
                "link_href": link_href,
            })

        return blocks
