import requests


class WikidataLinker:

    def __init__(self):
        self.cache = {}

    def link(self, entity):

        if entity in self.cache:
            return self.cache[entity]

        url = "https://www.wikidata.org/w/api.php"

        params = {
            "action": "wbsearchentities",
            "search": entity,
            "language": "es",
            "format": "json"
        }

        try:
            r = requests.get(url, params=params, timeout=5)

            if r.status_code != 200:
                return None

            data = r.json()

            if not data or "search" not in data:
                return None

            if data["search"]:
                top = data["search"][0]

                result = {
                    "id": top["id"],
                    "label": top["label"],
                    "description": top.get("description", "")
                }

                self.cache[entity] = result
                return result

        except Exception as e:
            print("Wikidata error:", e)

        return None

    def get_entity_data(self, wikidata_id):

        url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json"

        try:
            r = requests.get(url, timeout=5)

            if r.status_code != 200:
                return {}

            data = r.json()

            entity = data["entities"][wikidata_id]
            claims = entity.get("claims", {})

            props = {}

            # P31 → instance of
            if "P31" in claims:
                try:
                    props["instance_of"] = claims["P31"][0]["mainsnak"]["datavalue"]["value"]["id"]
                except Exception:
                    pass

            # P17 → country
            if "P17" in claims:
                try:
                    props["country"] = claims["P17"][0]["mainsnak"]["datavalue"]["value"]["id"]
                except Exception:
                    pass

            # P625 → coordinates
            if "P625" in claims:
                try:
                    coord = claims["P625"][0]["mainsnak"]["datavalue"]["value"]

                    lat = coord.get("latitude")
                    lon = coord.get("longitude")

                    if lat is not None and lon is not None:
                        props["latitude"] = lat
                        props["longitude"] = lon
                        props["coordinates"] = {
                            "lat": lat,
                            "lon": lon
                        }
                except Exception:
                    pass

            return props

        except Exception as e:
            print("Wikidata data error:", e)

        return {}