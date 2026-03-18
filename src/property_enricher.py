class PropertyEnricher:

    def __init__(self, ontology_index=None):
        self.ontology_index = ontology_index

    def enrich(self, entity, entity_class, text):

        props = {}

        # -------------------------
        # 🔥 PROPIEDADES BASE
        # -------------------------

        if entity_class == "Island":
            props["type"] = "Island"
            props["category"] = "GeographicalFeature"

        elif entity_class == "Municipality":
            props["type"] = "AdministrativeArea"

        elif entity_class == "Festival":
            props["eventType"] = "CulturalEvent"

        elif entity_class == "Ocean":
            props["type"] = "WaterBody"

        elif entity_class == "Valley":
            props["type"] = "NaturalFormation"

        else:
            props["type"] = "Location"

        # -------------------------
        # 🔥 CONTEXTO (MUY IMPORTANTE)
        # -------------------------

        if "gran canaria" in text.lower():
            props["locatedIn"] = "Gran Canaria"

        if any(x in text.lower() for x in ["delfines", "ballenas", "cetáceos"]):
            props["hasWildlife"] = "Cetaceans"

        # -------------------------
        # 🔥 ONTOLOGÍA (NUEVO)
        # -------------------------

        if self.ontology_index and entity_class:

            uri = self.ontology_index.get_class_uri(entity_class)

            if uri:
                ontology_props = self.ontology_index.get_class_properties(uri)

                for p in ontology_props:
                    prop_name = p["property"].split("#")[-1]

                    # evitar sobreescribir
                    if prop_name not in props:
                        props[prop_name] = "ontology"

        return props