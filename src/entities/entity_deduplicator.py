class EntityDeduplicator:

    def deduplicate(self, entities):

        seen = set()
        result = []

        for e in entities:

            key = e.lower().strip()

            if key not in seen:
                seen.add(key)
                result.append(e)

        return result