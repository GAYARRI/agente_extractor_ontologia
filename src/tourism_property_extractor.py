import json
import re
from bs4 import BeautifulSoup


class TourismPropertyExtractor:
    def __init__(self, properties=None, ontology_properties=None):
        if properties is None:
            properties = [
                "name",
                "description",
                "address",
                "telephone",
                "url",
                "latitude",
                "longitude",
                "openingHours",
            ]

        self.properties = properties
        self.ontology_properties = ontology_properties or {}

    # -----------------------------
    # Helpers
    # -----------------------------

    def _normalize(self, text: str) -> str:
        return " ".join(text.strip().lower().split())

    def _matches_entity(self, entity: str, candidate_name: str) -> bool:
        if not entity or not candidate_name:
            return False

        entity_norm = self._normalize(entity)
        candidate_norm = self._normalize(candidate_name)

        return entity_norm in candidate_norm or candidate_norm in entity_norm

    def _safe_get_nested(self, data, *keys):
        current = data
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        return current

    def _filter_allowed_properties(self, properties: dict) -> dict:
        clean = {}

        for k, v in properties.items():
            if v is None or v == "":
                continue

            if k in self.properties:
                clean[k] = v

        return clean

    # -----------------------------
    # JSON-LD extraction
    # -----------------------------

    def extract_jsonld(self, soup):
        results = []

        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            try:
                raw = script.string or script.get_text(strip=True)
                if not raw:
                    continue

                data = json.loads(raw)

                if isinstance(data, dict):
                    # algunos JSON-LD meten @graph
                    if "@graph" in data and isinstance(data["@graph"], list):
                        results.extend(data["@graph"])
                    else:
                        results.append(data)

                elif isinstance(data, list):
                    results.extend(data)

            except Exception:
                continue

        return results

    # -----------------------------
    # Meta tags extraction
    # -----------------------------

    def extract_meta(self, soup):
        props = {}

        for meta in soup.find_all("meta"):
            prop = meta.get("property") or meta.get("name")
            content = meta.get("content")

            if not content:
                continue

            if prop == "og:title":
                props["name"] = content

            elif prop == "og:description":
                props["description"] = content

            elif prop == "description" and "description" not in props:
                props["description"] = content

        return props

    # -----------------------------
    # GEO extraction
    # -----------------------------

    def extract_geo(self, text):
        geo = {}

        latlon = re.search(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", text)

        if latlon:
            geo["latitude"] = latlon.group(1)
            geo["longitude"] = latlon.group(2)

        return geo

    # -----------------------------
    # Address / phone fallback
    # -----------------------------

    def extract_contact_fallbacks(self, text):
        props = {}

        phone_match = re.search(r"(\+?\d[\d\s\-\(\)]{7,}\d)", text)
        if phone_match:
            props["telephone"] = phone_match.group(1).strip()

        return props

    # -----------------------------
    # Main extraction
    # -----------------------------

    def extract(self, html, text, url, entity):
        soup = BeautifulSoup(html, "html.parser")
        properties = {}

        # -----------------------------
        # JSON-LD
        # -----------------------------
        jsonld_data = self.extract_jsonld(soup)

        for item in jsonld_data:
            if not isinstance(item, dict):
                continue

            item_name = item.get("name")

            if item_name and self._matches_entity(entity, item_name):
                for prop in self.properties:
                    if prop in item:
                        properties[prop] = item[prop]

                geo = item.get("geo")
                if isinstance(geo, dict):
                    if "latitude" in geo:
                        properties["latitude"] = geo["latitude"]
                    if "longitude" in geo:
                        properties["longitude"] = geo["longitude"]

                address = item.get("address")
                if isinstance(address, dict):
                    address_parts = [
                        address.get("streetAddress"),
                        address.get("addressLocality"),
                        address.get("addressRegion"),
                        address.get("postalCode"),
                        address.get("addressCountry"),
                    ]
                    address_text = ", ".join([p for p in address_parts if p])
                    if address_text:
                        properties["address"] = address_text

        # -----------------------------
        # META tags
        # -----------------------------
        meta_props = self.extract_meta(soup)
        for k, v in meta_props.items():
            if k not in properties and v:
                properties[k] = v

        # -----------------------------
        # GEO fallback
        # -----------------------------
        geo = self.extract_geo(text)
        for k, v in geo.items():
            if k not in properties:
                properties[k] = v

        # -----------------------------
        # Contact fallback
        # -----------------------------
        contact_props = self.extract_contact_fallbacks(text)
        for k, v in contact_props.items():
            if k not in properties:
                properties[k] = v

        # -----------------------------
        # URL siempre presente
        # -----------------------------
        properties["url"] = url

        return self._filter_allowed_properties(properties)