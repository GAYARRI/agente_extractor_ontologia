import json
import re
from bs4 import BeautifulSoup


class TourismPropertyExtractor:

    def __init__(self, properties=None):

        if properties is None:

            properties = [
                "name",
                "description",
                "address",
                "telephone",
                "url",
                "latitude",
                "longitude",
                "openingHours"
            ]

        self.properties = properties


    # -----------------------------
    # JSON-LD extraction
    # -----------------------------

    def extract_jsonld(self, soup):

        results = []

        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:

            try:

                data = json.loads(script.string)

                if isinstance(data, dict):
                    results.append(data)

                if isinstance(data, list):
                    results.extend(data)

            except Exception:
                pass

        return results


    # -----------------------------
    # meta tags extraction
    # -----------------------------

    def extract_meta(self, soup):

        props = {}

        for meta in soup.find_all("meta"):

            if meta.get("property") == "og:title":
                props["name"] = meta.get("content")

            if meta.get("property") == "og:description":
                props["description"] = meta.get("content")

        return props


    # -----------------------------
    # geo extraction
    # -----------------------------

    def extract_geo(self, text):

        geo = {}

        latlon = re.search(
            r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)",
            text
        )

        if latlon:

            geo["latitude"] = latlon.group(1)
            geo["longitude"] = latlon.group(2)

        return geo


    # -----------------------------
    # main extraction
    # -----------------------------

    def extract(self, html, text, url, entity):

        soup = BeautifulSoup(html, "html.parser")

        properties = {}

        # -----------------------------
        # JSON-LD
        # -----------------------------

        jsonld_data = self.extract_jsonld(soup)

        for item in jsonld_data:

            if "name" in item and entity.lower() in item["name"].lower():

                for prop in self.properties:

                    if prop in item:
                        properties[prop] = item[prop]

                if "geo" in item:

                    geo = item["geo"]

                    if "latitude" in geo:
                        properties["latitude"] = geo["latitude"]

                    if "longitude" in geo:
                        properties["longitude"] = geo["longitude"]

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
        # URL
        # -----------------------------

        properties["url"] = url

        return properties