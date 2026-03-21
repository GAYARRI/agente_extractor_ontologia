import os
import re
from urllib.parse import urlparse, urlunparse, unquote


class ImageEnricher:
    def __init__(self):
        pass

    # ==================================================
    # HELPERS
    # ==================================================

    def _normalize_image_url(self, url):
        if not url:
            return None

        url = str(url).strip()
        if not url:
            return None

        parsed = urlparse(url)

        clean = urlunparse((
            parsed.scheme,
            parsed.netloc,
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
        return (
            "wikimedia.org" in low
            or "wikipedia.org" in low
            or "wikidata.org" in low
            or "commons.wikimedia.org" in low
        )

    def _is_probably_image_url(self, url):
        if not url:
            return False

        low = url.lower()
        return any(ext in low for ext in [
            ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"
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

    # ==================================================
    # EXTRACT
    # ==================================================

    def enrich(self, entity, text):
        """
        Este enriquecedor NO debe volver a meter las imágenes locales de la página.
        Su misión aquí será, sobre todo, separar posibles imágenes externas/Wikidata
        en un campo distinto: wikidataImage.
        """

        if not text:
            return {}

        # Buscar URLs de imagen explícitas en el texto, si apareciesen
        urls = re.findall(r'https?://[^\s<>"\']+', text)
        image_urls = [u for u in urls if self._is_probably_image_url(u)]

        if not image_urls:
            return {}

        image_urls = self._dedupe_images(image_urls)

        # separar wikimedia del resto
        wikimedia_images = [u for u in image_urls if self._is_wikimedia_url(u)]
        local_or_other_images = [u for u in image_urls if not self._is_wikimedia_url(u)]

        props = {}

        # Solo como fallback: si este módulo encuentra imágenes no wiki
        # y no vienen de la página, las deja en additionalImages
        if local_or_other_images:
            props["additionalImages"] = local_or_other_images

        # La de wikidata/wikimedia siempre separada
        if wikimedia_images:
            props["wikidataImage"] = wikimedia_images[0]

        return props