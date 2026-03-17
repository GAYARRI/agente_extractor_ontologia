class PropertyEnricher:

    def enrich(self, entity, entity_class, text):

        props = {}

        # -------------------------
        # PROPIEDADES POR CLASE
        # -------------------------

        if entity_class == "Festival":
            props["eventType"] = "CulturalEvent"

        elif entity_class == "ReligiousEvent":
            props["eventType"] = "ReligiousEvent"

        elif entity_class == "Island":
            props["type"] = "Island"
            props["category"] = "GeographicalFeature"

        elif entity_class == "Municipality":
            props["type"] = "AdministrativeArea"

        elif entity_class == "NaturalArea":
            props["type"] = "NaturalArea"

        elif entity_class == "Marina":
            props["type"] = "Port"

        elif entity_class == "Ocean":
            props["type"] = "WaterBody"

        elif entity_class == "Valley":
            props["type"] = "NaturalFormation"

        elif entity_class == "Place":
            props["type"] = "Location"

        # -------------------------
        # CONTEXTO
        # -------------------------

        t = text.lower()

        if "gran canaria" in t:
            props["locatedIn"] = "Gran Canaria"

        if "atlántico" in t:
            props["nearWater"] = "Atlantic Ocean"

        if "delfines" in t or "ballenas" in t:
            props["hasWildlife"] = "Cetaceans"

        # -------------------------
        # FALLBACK
        # -------------------------

        if not props:
            props["type"] = "Thing"

        return props