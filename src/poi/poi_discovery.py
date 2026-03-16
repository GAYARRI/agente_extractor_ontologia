import json


class POIDiscovery:

    def __init__(self, gazetteer_path="data/spanish_municipalities.json"):

        try:
            with open(gazetteer_path, "r", encoding="utf-8") as f:
                self.municipalities = set(json.load(f))
        except:
            self.municipalities = set()

    def discover(self, text):

        discovered = []

        text_lower = text.lower()

        for place in self.municipalities:

            if place.lower() in text_lower:
                discovered.append(place)

        return discovered