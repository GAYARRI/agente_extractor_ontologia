import json
from bs4 import BeautifulSoup


class StructuredDataExtractor:

    def extract(self, html):

        soup = BeautifulSoup(html, "html.parser")

        entities = []
        properties = []

        # ----------------------------
        # 1️⃣ JSON-LD (schema.org)
        # ----------------------------

        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:

            try:
                data = json.loads(script.string)

                if isinstance(data, list):
                    items = data
                else:
                    items = [data]

                for item in items:

                    name = item.get("name")
                    entity_type = item.get("@type")

                    if name:
                        entities.append({
                            "name": name,
                            "type": entity_type
                        })

                    # geo coordinates
                    geo = item.get("geo")

                    if geo:

                        lat = geo.get("latitude")
                        lon = geo.get("longitude")

                        if lat and lon:

                            properties.append({
                                "entity": name,
                                "property": "geo",
                                "value": (lat, lon)
                            })

                    # image
                    image = item.get("image")

                    if image:

                        properties.append({
                            "entity": name,
                            "property": "image",
                            "value": image
                        })

            except Exception:
                pass


        # ----------------------------
        # 2️⃣ OpenGraph
        # ----------------------------

        og_title = soup.find("meta", property="og:title")
        og_type = soup.find("meta", property="og:type")
        og_image = soup.find("meta", property="og:image")

        if og_title:

            name = og_title.get("content")

            entities.append({
                "name": name,
                "type": og_type.get("content") if og_type else None
            })

            if og_image:

                properties.append({
                    "entity": name,
                    "property": "image",
                    "value": og_image.get("content")
                })


        # ----------------------------
        # 3️⃣ geo meta tags
        # ----------------------------

        lat = soup.find("meta", property="place:location:latitude")
        lon = soup.find("meta", property="place:location:longitude")

        if lat and lon:

            properties.append({
                "property": "geo",
                "value": (lat.get("content"), lon.get("content"))
            })


        return {
            "entities": entities,
            "properties": properties
        }