import os
import re
from urllib.parse import urlparse, urlunparse, unquote


class ImageEnricher:
    def __init__(self):
        pass

    # ==================================================
    # HELPERS
    # ==================================================

    def _normalize_text(self, text):
        return " ".join((text or "").strip().lower().split())

    def _entity_tokens(self, text):
        text = self._normalize_text(text)
        text = re.sub(r"[^a-z0-9áéíóúñü\s\-_/]", " ", text)
        return {t for t in text.replace("-", " ").replace("/", " ").split() if len(t) >= 3}

    def _normalize_image_url(self, url):
        if not url:
            return None

        url = str(url).strip()
        if not url:
            return None

        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return None

        clean = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            "",
            "",
            ""
        ))

        return unquote(clean)

    def _image_signature(self, url):
        if not url:
            return None

        norm = self._normalize_image_url(url)
        if not norm:
            return None

        path = unquote(urlparse(norm).path).lower()
        filename = os.path.basename(path)

        if not filename:
            return path

        thumb_prefixes = [
            "120px-", "150px-", "180px-", "200px-", "220px-", "250px-",
            "300px-", "320px-", "400px-", "500px-", "640px-", "800px-",
            "1024px-"
        ]

        for prefix in thumb_prefixes:
            if filename.startswith(prefix):
                filename = filename[len(prefix):]
                break

        return filename

    def _is_wikimedia_url(self, url):
        if not url:
            return False

        low = url.lower()
        return any(host in low for host in [
            "wikimedia.org",
            "wikipedia.org",
            "wikidata.org",
            "commons.wikimedia.org",
        ])

    def _is_probably_image_url(self, url):
        if not url:
            return False

        low = url.lower()

        if any(ext in low for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]):
            return True

        return False

    def _is_probably_logo(self, url: str) -> bool:
        if not url:
            return True

        u = url.lower()

        bad_patterns = [
            "logo", "icon", "sprite", "banner", "placeholder",
            "default", "avatar", "marca", "brand", "header",
            "footer", "og-image", "share", "social"
        ]

        return any(p in u for p in bad_patterns)    
        

    def _dedupe_images(self, urls):
        result = []
        seen = set()

        for url in urls:
            norm = self._normalize_image_url(url)
            sig = self._image_signature(norm)

            if not norm or not sig:
                continue

            if sig in seen:
                continue

            seen.add(sig)
            result.append(norm)

        return result

    def _image_relevance_score(self, entity, image_url, text=""):
        """
        Intenta evitar imágenes ajenas a la instancia.
        No es perfecto, pero ayuda a filtrar URLs demasiado genéricas.
        """
        if not image_url:
            return -10

        if self._is_probably_logo(image_url):
            return -10

        entity_tokens = self._entity_tokens(entity)
        if not entity_tokens:
            return 0

        bag = set()
        bag.update(self._entity_tokens(image_url))
        bag.update(self._entity_tokens(text))

        overlap = len(entity_tokens & bag)

        score = 0
        score += overlap * 3

        # pequeña penalización si parece muy genérica
        generic_tokens = {"image", "images", "photo", "photos", "gallery", "media", "upload"}
        if bag & generic_tokens:
            score -= 1

        return score

    # ==================================================
    # EXTRACT
    # ==================================================

    def enrich(self, entity, text="", html="", url=""):
        """
        Devuelve una imagen razonable para la entidad.
        Prioridad:
        1) imágenes explícitas en el texto
        2) JSON-LD / schema.org
        3) og:image SOLO como fallback débil
        """

        candidates = []

        if text:
            urls = re.findall(r'https?://[^\s<>"\']+', text)
            text_images = [u for u in urls if self._is_probably_image_url(u)]
            candidates.extend(text_images)

        jsonld_images = []
        og_image = ""

        if html:
            jsonld_images = self._extract_jsonld_images(html)
            og_image = self._extract_og_image(html)

        # Primero intentamos con imágenes más específicas
        candidates.extend(jsonld_images)
        candidates = self._dedupe_images(candidates)

        best = self._choose_best_image(entity, candidates, text=text)
        if best:
            return {"image": best}

        # og:image solo como fallback
        if og_image and not self._is_probably_logo(og_image):
            return {"image": og_image}

        return {}
    
        
    

    def _extract_og_image(self, html: str) -> str:
        if not html:
            return ""
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE
        )
        return m.group(1).strip() if m else ""

    def _extract_jsonld_images(self, html: str) -> list:
        if not html:
            return []
        matches = re.findall(r'"image"\s*:\s*"([^"]+)"', html, re.IGNORECASE)
        return [m.strip() for m in matches if m.strip()]

    def _choose_best_image(self, entity: str, candidates: list, text: str = "") -> str:
        valid = []

        entity_norm = (entity or "").strip().lower()

        for img in candidates:
            if not img:
                continue
            if self._is_probably_logo(img):
                continue

            score = self._image_relevance_score(entity, img, text=text)

            u = img.lower()

            if self._is_wikimedia_url(img):
                score += 1

            # penalizaciones por imagen demasiado genérica
            generic_hits = [
                "visitasevilla",
                "cabecera",
                "header",
                "home",
                "portada",
                "generic",
                "default",
                "banner"
            ]
            if any(g in u for g in generic_hits):
                score -= 3

            # premio si el nombre de la entidad aparece en la URL
            tokens = [t for t in re.split(r"[\s\-_]+", entity_norm) if len(t) > 3]
            if tokens and any(t in u for t in tokens):
                score += 3

            valid.append((img, score))

        if not valid:
            return ""

        valid.sort(key=lambda x: x[1], reverse=True)
        return valid[0][0]