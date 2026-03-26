import re
from bs4 import BeautifulSoup


class TourismPropertyExtractor:
    """
    Extractor conservador:
    - NO usa la primera imagen global de la página.
    - SOLO acepta phone/email/address si aparecen cerca del bloque de la entidad.
    - Si no hay evidencia local, devuelve poco antes que contaminar.
    """

    CONTACT_WINDOW = 280

    def __init__(self, class_properties):
        self.class_properties = class_properties

    def _clean(self, text: str) -> str:
        text = text or ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _find_local_window(self, text: str, entity_name: str) -> str:
        text = self._clean(text)
        entity_name = self._clean(entity_name)

        if not text or not entity_name:
            return text

        idx = text.lower().find(entity_name.lower())
        if idx == -1:
            return text[: self.CONTACT_WINDOW * 2]

        start = max(0, idx - self.CONTACT_WINDOW)
        end = min(len(text), idx + len(entity_name) + self.CONTACT_WINDOW)
        return text[start:end]

    def _extract_first_email(self, text: str) -> str:
        m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text, flags=re.IGNORECASE)
        return m.group(0) if m else ""

    def _extract_first_phone(self, text: str) -> str:
        patterns = [
            r'(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3}[\s\-]?\d{3}[\s\-]?\d{3}',
            r'(?:\+?\d{1,3}[\s\-]?)?\d{9}',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                value = m.group(0).strip()
                if len(re.sub(r"\D", "", value)) >= 9:
                    return value
        return ""

    def _extract_first_address(self, text: str) -> str:
        patterns = [
            r'\b(?:calle|c/|avenida|avda\.?|plaza|paseo|alameda|alcalde)\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\-\s]+',
            r'\b[A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]+,\s*\d{1,4}\b',
        ]
        for p in patterns:
            m = re.search(p, text, flags=re.IGNORECASE)
            if m:
                return self._clean(m.group(0))
        return ""

    def _extract_coords(self, html: str) -> dict:
        lat = re.search(r'lat["\': ]+([0-9.\-]+)', html)
        lon = re.search(r'lon["\': ]+([0-9.\-]+)', html)
        if lat and lon:
            return {
                "geoLat": lat.group(1),
                "geoLong": lon.group(1),
            }
        return {}

    def _extract_entity_image(self, soup: BeautifulSoup, entity_name: str) -> str:
        """
        Conservador: intenta encontrar una imagen cercana semánticamente,
        pero NO toma la primera imagen global de la página.
        """
        entity_name_l = (entity_name or "").lower().strip()
        if not entity_name_l:
            return ""

        # busca imágenes cuyo alt/title/data-caption contenga la entidad
        for img in soup.find_all("img"):
            attrs = " ".join(
                filter(
                    None,
                    [
                        img.get("alt", ""),
                        img.get("title", ""),
                        img.get("aria-label", ""),
                        img.get("data-caption", ""),
                    ],
                )
            ).lower()

            src = img.get("src") or img.get("data-src") or ""
            if entity_name_l in attrs and src:
                return src.strip()

        return ""

    def extract(self, html, text, url, entity):
        properties = {}
        entity_class = entity.get("class", "")
        entity_name = entity.get("entity_name") or entity.get("entity") or entity.get("name") or ""

        if entity_class not in self.class_properties:
            return properties

        soup = BeautifulSoup(html or "", "html.parser")
        local_text = self._find_local_window(text or "", entity_name)

        # -------- imagen local solo si hay match semántico --------
        image = self._extract_entity_image(soup, entity_name)
        if image:
            properties["image"] = image

        # -------- coordenadas --------
        coords = self._extract_coords(html or "")
        
        if not coords:
            coords = self._extract_coords_from_google_maps(html or "")

        properties.update(coords)

        # -------- propiedades locales y conservadoras --------
        hours = re.search(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', local_text)
        if hours:
            properties["openingHours"] = hours.group(0)

        price = re.search(r'(\d+)\s?€', local_text)
        if price:
            properties["price"] = price.group(0)

        address = self._extract_first_address(local_text)
        if address:
            properties["address"] = address

        phone = self._extract_first_phone(local_text)
        if phone:
            properties["telephone"] = phone

        email = self._extract_first_email(local_text)
        if email:
            properties["email"] = email

        rating = re.search(r'([0-5]\.?[0-9]?)\s?/5', local_text)
        if rating:
            properties["rating"] = rating.group(1)
  

        return properties
    
    def _extract_coords_from_google_maps(self, html: str) -> dict:
        import re

        # patrón típico de Google Maps embed
        match = re.search(r'@([-0-9.]+),([-0-9.]+)', html)
        if match:
            return {
                "geoLat": match.group(1),
                "geoLong": match.group(2),
            }

        # patrón tipo q=lat,lon
        match = re.search(r'q=([-0-9.]+),([-0-9.]+)', html)
        if match:
            return {
                "geoLat": match.group(1),
                "geoLong": match.group(2),
            }

        return {}