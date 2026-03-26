import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class TourismPropertyExtractor:
    """
    Extractor conservador de propiedades turísticas.

    Objetivos:
    - NO contaminar entidades con datos globales del portal/footer.
    - Priorizar texto local al bloque donde aparece la entidad.
    - Extraer solo propiedades con evidencia cercana a la entidad.
    - Mantener compatibilidad con TourismPipeline(): TourismPropertyExtractor()
      y extract(html, text, url, entity).
    """

    CONTACT_WINDOW = 280

    PORTAL_TEXT_BLOCKLIST = {
        "visita sevilla",
        "te queda mucho por descubrir",
        "te queda mucho por descubrir:",
        "estudiar en sevilla - visita sevilla",
        "el flamenco - visita sevilla",
    }

    GENERIC_IMAGE_FRAGMENTS = {
        "el-flamenco-bloque-2.jpg",
    }

    PERSON_CLASSES = {"Person"}
    NO_CONTACT_CLASSES = {"Person", "Concept", "Thing"}
    ALLOW_COORD_CLASSES = {
        "Place",
        "Location",
        "TouristAttraction",
        "Landmark",
        "Organization",
        "Service",
        "LocalBusiness",
    }

    ADDRESS_RE_LIST = [
        r"\b(?:calle|c/|avenida|avda\.?|plaza|paseo|alameda|alcalde|carretera|camino)\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\-\s]+",
        r"\b[A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]+,\s*\d{1,4}\b",
    ]

    PHONE_RE_LIST = [
        r"(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3}[\s\-]?\d{3}[\s\-]?\d{3}",
        r"(?:\+?\d{1,3}[\s\-]?)?\d{9}",
    ]

    EMAIL_RE = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

    def _clean(self, text: str) -> str:
        text = text or ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _norm(self, text: str) -> str:
        return self._clean(text).lower()

    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        return self._clean(str(value))

    def _entity_name(self, entity: Dict[str, Any]) -> str:
        return (
            self._safe_str(entity.get("entity_name"))
            or self._safe_str(entity.get("entity"))
            or self._safe_str(entity.get("name"))
        )

    def _entity_class(self, entity: Dict[str, Any]) -> str:
        return self._safe_str(entity.get("class")) or "Thing"

    def _find_local_window(self, text: str, entity_name: str) -> str:
        text = self._clean(text)
        entity_name = self._clean(entity_name)
        if not text:
            return ""
        if not entity_name:
            return text[: self.CONTACT_WINDOW * 2]

        idx = text.lower().find(entity_name.lower())
        if idx == -1:
            return text[: self.CONTACT_WINDOW * 2]

        start = max(0, idx - self.CONTACT_WINDOW)
        end = min(len(text), idx + len(entity_name) + self.CONTACT_WINDOW)
        return text[start:end]

    def _contains_portal_noise(self, value: str) -> bool:
        v = self._norm(value)
        return not v or v in self.PORTAL_TEXT_BLOCKLIST

    def _extract_email(self, text: str) -> str:
        m = re.search(self.EMAIL_RE, text, flags=re.IGNORECASE)
        return m.group(0).strip() if m else ""

    def _extract_phone(self, text: str) -> str:
        for pattern in self.PHONE_RE_LIST:
            m = re.search(pattern, text)
            if m:
                value = m.group(0).strip()
                digits = re.sub(r"\D", "", value)
                if len(digits) >= 9:
                    return value
        return ""

    def _extract_address(self, text: str) -> str:
        for pattern in self.ADDRESS_RE_LIST:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                value = self._clean(m.group(0))
                if not self._contains_portal_noise(value):
                    return value
        return ""

    def _extract_hours(self, text: str) -> str:
        m = re.search(r"(\d{1,2}:\d{2})\s*[-–a]\s*(\d{1,2}:\d{2})", text, flags=re.IGNORECASE)
        return m.group(0).strip() if m else ""

    def _extract_price(self, text: str) -> str:
        m = re.search(r"(\d+[\.,]?\d*)\s?€", text)
        return m.group(0).strip() if m else ""

    def _extract_rating(self, text: str) -> str:
        m = re.search(r"([0-5](?:[\.,][0-9])?)\s*/\s*5", text)
        return m.group(1).replace(",", ".") if m else ""

    def _extract_coords_from_text(self, text: str) -> Dict[str, Any]:
        # lat/lon explícitos
        m = re.search(r"(?:lat|latitude)[\s:=]+([-0-9.]+).{0,25}(?:lon|lng|longitude)[\s:=]+([-0-9.]+)", text, flags=re.IGNORECASE)
        if m:
            try:
                return {"geoLat": float(m.group(1)), "geoLong": float(m.group(2))}
            except Exception:
                pass

        # formato @lat,lon de mapas
        m = re.search(r"@([-0-9.]+),([-0-9.]+)", text)
        if m:
            try:
                return {"geoLat": float(m.group(1)), "geoLong": float(m.group(2))}
            except Exception:
                pass

        # q=lat,lon
        m = re.search(r"q=([-0-9.]+),([-0-9.]+)", text)
        if m:
            try:
                return {"geoLat": float(m.group(1)), "geoLong": float(m.group(2))}
            except Exception:
                pass

        return {}

    def _extract_coords(self, html: str, local_text: str) -> Dict[str, Any]:
        html = html or ""
        for source in [local_text or "", html]:
            coords = self._extract_coords_from_text(source)
            if coords:
                return coords
        return {}

    def _img_src(self, img_tag, base_url: str) -> str:
        src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src") or ""
        src = self._safe_str(src)
        if not src:
            return ""
        return urljoin(base_url or "", src)

    def _image_is_generic(self, src: str) -> bool:
        src_l = (src or "").lower()
        return any(fragment in src_l for fragment in self.GENERIC_IMAGE_FRAGMENTS)

    def _find_candidate_images(self, soup: BeautifulSoup, entity_name: str, base_url: str) -> List[str]:
        entity_l = self._norm(entity_name)
        candidates = []

        for img in soup.find_all("img"):
            attrs_text = " ".join(
                filter(
                    None,
                    [
                        img.get("alt", ""),
                        img.get("title", ""),
                        img.get("aria-label", ""),
                        img.get("data-caption", ""),
                    ],
                )
            )
            attrs_l = self._norm(attrs_text)
            src = self._img_src(img, base_url)
            if not src or self._image_is_generic(src):
                continue

            if entity_l and entity_l in attrs_l:
                candidates.append(src)
                continue

            # padre/cercanía textual
            parent_text = self._norm(img.parent.get_text(" ", strip=True) if img.parent else "")
            if entity_l and entity_l in parent_text:
                candidates.append(src)

        # dedupe preservando orden
        out = []
        seen = set()
        for c in candidates:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _extract_entity_image(self, soup: BeautifulSoup, entity_name: str, base_url: str) -> str:
        candidates = self._find_candidate_images(soup, entity_name, base_url)
        return candidates[0] if candidates else ""

    def _extract_related_urls(self, soup: BeautifulSoup, entity_name: str, base_url: str) -> List[str]:
        entity_l = self._norm(entity_name)
        urls = []
        for a in soup.find_all("a", href=True):
            anchor_text = self._norm(a.get_text(" ", strip=True))
            href = self._safe_str(a.get("href"))
            if not href:
                continue
            if entity_l and entity_l in anchor_text:
                urls.append(urljoin(base_url or "", href))

        out = []
        seen = set()
        for u in urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def extract(self, html, text, url, entity):
        properties = {}

        # Acepta entity como dict o como string
        if isinstance(entity, dict):
            entity_name = (
                entity.get("entity_name")
                or entity.get("entity")
                or entity.get("name")
                or entity.get("label")
                or ""
            )
            entity_class = entity.get("class", "")
        elif isinstance(entity, str):
            entity_name = entity.strip()
            entity_class = ""
        else:
            entity_name = ""
            entity_class = ""

        if not entity_name:
            return properties

        soup = BeautifulSoup(html or "", "html.parser")
        full_text = text or ""

        # descripción local
        if full_text:
            properties["description"] = full_text[:500]

        # url fuente
        if url:
            properties["url"] = url

        # imagen local si la encuentras
        try:
            image = self._extract_entity_image(soup, entity_name)
            if image:
                properties["image"] = image
                properties["mainImage"] = image
        except Exception:
            pass

        # email/teléfono/dirección solo si aparecen en contexto local
        try:
            local_text = self._find_local_window(full_text, entity_name)
        except Exception:
            local_text = full_text

        try:
            email = self._extract_first_email(local_text)
            if email:
                properties["email"] = email
        except Exception:
            pass

        try:
            phone = self._extract_first_phone(local_text)
            if phone:
                properties["telephone"] = phone
        except Exception:
            pass

        try:
            address = self._extract_first_address(local_text)
            if address:
                properties["address"] = address
        except Exception:
            pass

        # coordenadas si existen en HTML
        try:
            coords = self._extract_coords(html or "")
            if coords:
                properties.update(coords)
        except Exception:
            pass

        return properties    