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

    def _is_probably_logo(self, url):
        if not url:
            return False

        low = url.lower()
        return any(token in low for token in [
            "logo", "icon", "avatar", "sprite", "favicon", "placeholder"
        ])

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

    def enrich(self, entity, text):
        """
        Este enriquecedor NO debe volver a meter las imágenes locales de la página.
        Su misión aquí será, sobre todo:
        - detectar URLs explícitas de imagen en el texto
        - separar imágenes Wikimedia/Wikidata en wikidataImage
        - dejar otras imágenes externas como fallback en additionalImages
        """

        if not text:
            return {}

        urls = re.findall(r'https?://[^\s<>"\']+', text)
        image_urls = [u for u in urls if self._is_probably_image_url(u)]

        if not image_urls:
            return {}

        image_urls = self._dedupe_images(image_urls)

        # filtrar logos / iconos / imágenes claramente irrelevantes
        filtered_images = []
        for img in image_urls:
            if self._is_probably_logo(img):
                continue

            score = self._image_relevance_score(entity, img, text=text)

            # Wikimedia se permite incluso con score bajo porque suele ser externa y útil
            if self._is_wikimedia_url(img):
                filtered_images.append(img)
                continue

            # Para el resto, exigir algo mínimo de relación
            if score >= 1:
                filtered_images.append(img)

        if not filtered_images:
            return {}

        wikimedia_images = [u for u in filtered_images if self._is_wikimedia_url(u)]
        local_or_other_images = [u for u in filtered_images if not self._is_wikimedia_url(u)]

        props = {}

        # Mantener separada la imagen de Wikidata/Wikimedia
        if wikimedia_images:
            props["wikidataImage"] = wikimedia_images[0]

        # Solo como fallback, no demasiadas
        if local_or_other_images:
            props["additionalImages"] = local_or_other_images[:3]

        return props