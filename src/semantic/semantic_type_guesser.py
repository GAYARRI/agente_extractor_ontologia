import json
import os


class SemanticTypeGuesser:

    def __init__(self, municipalities_path="data/spanish_municipalities.json"):

        self.places = {
        "gran canaria": "Island",
        "maspalomas": "TouristDestination",
        "pasito blanco": "Marina",
        "san bartolomé de tirajana": "Municipality"
    }


        self.municipalities = set()

        if os.path.exists(municipalities_path):

            try:
                with open(municipalities_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    # guardamos en minúsculas para comparar mejor
                    self.municipalities = {m.lower() for m in data}

            except Exception:
                self.municipalities = set()


    def guess(self, entity):

        e = entity.lower()

        # -------- EVENTOS --------

        if "romería" in e:
            return "ReligiousEvent"

        if "semana santa" in e:
            return "ReligiousEvent"

        if "fiesta" in e:
            return "Festival"

        # -------- LUGARES --------

        if "playa" in e:
            return "Beach"

        if "observatorio" in e:
            return "InterpretationCentre"

        # -------- MUNICIPIOS --------

        if e in self.municipalities:
            return "TouristDestination"

        # -------- HEURÍSTICA DE TOPÓNIMOS --------

        if " de " in e and entity[0].isupper():
            return "TouristDestination"
        
        if "sibera" in e:
            return "TouristDestination"
        
        if entity.lower() in self.places:
            return self.places[entity.lower()]

        return None