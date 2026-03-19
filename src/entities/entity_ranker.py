class EntityRanker:

    def __init__(self):
        pass

    # ==================================================
    # SCORE FINAL
    # ==================================================
    def compute_score(self, entity_data, text):

        base = entity_data.get("score", 0.5)

        entity = entity_data.get("entity", "").lower()

        bonus = 0

        # 🔥 aparece en texto varias veces
        count = text.lower().count(entity)
        bonus += min(count * 0.1, 0.3)

        # 🔥 longitud buena
        if 2 <= len(entity.split()) <= 4:
            bonus += 0.1

        # 🔥 wikidata
        if "wikidata" in entity_data.get("properties", {}):
            bonus += 0.2

        # 🔥 penalización ruido
        if any(x in entity for x in [
            "disfruta", "descubre", "todo", "info", "click"
        ]):
            bonus -= 0.3

        return max(0, min(1, base + bonus))

    # ==================================================
    # NORMALIZACIÓN CLAVE
    # ==================================================
    def normalize_key(self, entity):

        return entity.lower().strip()

    # ==================================================
    # FUSIÓN
    # ==================================================
    def merge_entities(self, entities):

        merged = {}

        for e in entities:

            key = self.normalize_key(e["entity"])

            if key not in merged:
                merged[key] = e
            else:
                # 🔥 nos quedamos con el mejor score
                if e["score"] > merged[key]["score"]:
                    merged[key] = e

        return list(merged.values())

    # ==================================================
    # RANKING COMPLETO
    # ==================================================
    def rank(self, entities, text):

        for e in entities:
            e["score"] = self.compute_score(e, text)

        # ordenar
        entities = sorted(entities, key=lambda x: x["score"], reverse=True)

        # fusionar duplicados
        entities = self.merge_entities(entities)

        # 🔥 filtro final (top calidad)
        entities = [e for e in entities if e["score"] > 0.4]

        return entities