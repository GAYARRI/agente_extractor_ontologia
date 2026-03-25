import re
from urllib.parse import urljoin


class ImageEnricher:
    def __init__(self):
        pass

    # =========================================================
    # Helpers
    # =========================================================

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _tokens(self, text: str):
        text = self._normalize(text)
        return [t for t in re.split(r"[\s\-_/,.;:()]+", text) if len(t) > 3]

    def _is_probably_image_url(self, url: str) -> bool:
        if not url:
            return False
        u = url.lower()
        return any(ext in u for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"])

    def _is_probably_logo(self, url: str) -> bool:
        if not url:
            return True

        u = url.lower()
        bad_patterns = [
            "logo", "icon", "sprite", "banner", "placeholder",
            "default", "avatar", "header", "footer",
            "og-image", "share", "social",
            "separador", "separator"
        ]
        return any(p in u for p in bad_patterns)

    def _extract_img_tags(self, html: str):
        if not html:
            return []

        pattern = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
        return pattern.findall(html)

    def _extract_attr(self, tag: str, attr: str) -> str:
        if not tag:
            return ""

        patterns = [
            rf'{attr}\s*=\s*"([^"]+)"',
            rf"{attr}\s*=\s*'([^']+)'",
        ]
        for p in patterns:
            m = re.search(p, tag, re.IGNORECASE)
            if m:
                return m.group(1).strip()

        return ""

    def _get_img_src(self, tag: str, base_url: str = "") -> str:
        src = (
            self._extract_attr(tag, "src")
            or self._extract_attr(tag, "data-src")
            or self._extract_attr(tag, "data-lazy-src")
        )

        if not src:
            srcset = self._extract_attr(tag, "srcset")
            if srcset:
                src = srcset.split(",")[0].split(" ")[0].strip()

        if src and base_url:
            src = urljoin(base_url, src)

        return src

    def _image_relevance_score(self, entity: str, src: str, alt: str = "", title: str = "", text: str = "") -> int:
        score = 0

        entity_tokens = self._tokens(entity)
        src_l = self._normalize(src)
        alt_l = self._normalize(alt)
        title_l = self._normalize(title)
        text_l = self._normalize(text)

        if self._is_probably_logo(src):
            score -= 10

        if any(t in alt_l for t in entity_tokens):
            score += 5

        if any(t in title_l for t in entity_tokens):
            score += 4

        if any(t in src_l for t in entity_tokens):
            score += 3

        if entity_tokens and any(t in text_l for t in entity_tokens):
            score += 1

        if src_l.endswith(".jpg") or src_l.endswith(".jpeg") or src_l.endswith(".webp"):
            score += 1

        # penalizar imágenes muy globales
        generic_hits = [
            "visitasevilla",
            "home",
            "portada",
            "hero",
            "cabecera",
            "header",
            "cover",
            "pumarejo",
        ]
        if any(g in src_l for g in generic_hits):
            score -= 3

        return score

    def _dedupe_images(self, images):
        out = []
        seen = set()

        for img in images:
            if not img:
                continue
            key = img.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)

        return out

    def _extract_text_image_urls(self, text: str):
        if not text:
            return []

        urls = re.findall(r'https?://[^\s<>"\']+', text)
        return [u for u in urls if self._is_probably_image_url(u)]

    def _extract_candidates_from_html(self, html: str, entity: str, base_url: str = "", text: str = ""):
        candidates = []
        img_tags = self._extract_img_tags(html)

        for tag in img_tags:
            src = self._get_img_src(tag, base_url=base_url)
            if not src:
                continue
            if not self._is_probably_image_url(src):
                continue

            alt = self._extract_attr(tag, "alt")
            title = self._extract_attr(tag, "title")
            score = self._image_relevance_score(entity, src, alt=alt, title=title, text=text)
            candidates.append((src, score))

        return candidates

    def _best_candidate(self, candidates):
        if not candidates:
            return "", 0

        best_by_src = {}
        for src, score in candidates:
            if src not in best_by_src or score > best_by_src[src]:
                best_by_src[src] = score

        ordered = sorted(best_by_src.items(), key=lambda x: x[1], reverse=True)
        return ordered[0]

    # =========================================================
    # API pública
    # =========================================================

    def enrich(self, entity, text="", html="", url=""):
        """
        Muy conservador:
        - usa imágenes explícitas en el texto si existen
        - usa imágenes del HTML solo si tienen evidencia razonable
        - NO usa og:image como fallback global
        """

        candidates = []

        # 1) URLs de imagen explícitas en el texto
        text_images = self._extract_text_image_urls(text)
        for img in text_images:
            score = self._image_relevance_score(entity, img, text=text) + 2
            candidates.append((img, score))

        # 2) Imágenes del HTML con scoring semántico
        html_candidates = self._extract_candidates_from_html(html, entity, base_url=url, text=text)
        candidates.extend(html_candidates)

        # limpiar
        cleaned = []
        for src, score in candidates:
            if not src:
                continue
            if self._is_probably_logo(src):
                continue
            cleaned.append((src, score))

        if not cleaned:
            return {}

        src, score = self._best_candidate(cleaned)

        # umbral conservador:
        # solo devolvemos si hay evidencia media-alta
        if score >= 4:
            return {
                "image": src,
                "mainImage": src,
            }

        # confianza media: no la promovemos a imagen final
        if score == 3:
            return {
                "candidateImage": src,
            }

        return {}