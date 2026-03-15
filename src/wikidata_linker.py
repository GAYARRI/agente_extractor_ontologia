import requests


class WikidataLinker:

    def __init__(self):
        self.endpoint = "https://www.wikidata.org/w/api.php"

    def search(self, label):

        params = {
            "action": "wbsearchentities",
            "search": label,
            "language": "es",
            "format": "json",
            "limit": 1
        }

        try:

            r = requests.get(self.endpoint, params=params)

            data = r.json()

            if "search" not in data:
                return None

            if len(data["search"]) == 0:
                return None

            item = data["search"][0]

            return f"http://www.wikidata.org/entity/{item['id']}"

        except:
            return None