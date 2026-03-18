class EntityDescriptionConsolidator:

    def consolidate(self, results):

        entity_map = {}

        for block in results:
            for e in block.get("entities", []):

                key = e["entity"].lower()

                if key not in entity_map:
                    entity_map[key] = {
                        "entity": e["entity"],
                        "class": e["class"],
                        "score": e["score"],
                        "properties": e.get("properties", {}),
                        "short_descriptions": [],
                        "long_descriptions": []
                    }

                # acumular descripciones
                sd = e.get("short_description")
                ld = e.get("long_description")

                if sd:
                    entity_map[key]["short_descriptions"].append(sd)

                if ld:
                    entity_map[key]["long_descriptions"].append(ld)

        # 🔥 elegir mejor descripción
        consolidated = []

        for e in entity_map.values():

            best_short = self._select_best(e["short_descriptions"])
            best_long = self._select_best(e["long_descriptions"])

            consolidated.append({
                "entity": e["entity"],
                "class": e["class"],
                "score": e["score"],
                "properties": e["properties"],
                "short_description": best_short,
                "long_description": best_long
            })

        return consolidated

    def _select_best(self, descriptions):

        if not descriptions:
            return ""

        # 🔥 heurística: la más larga (mejor información)
        return sorted(descriptions, key=len, reverse=True)[0]