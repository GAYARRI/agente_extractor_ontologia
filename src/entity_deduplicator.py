class EntityDeduplicator:

    def deduplicate(self, entities):

        if not entities:
            return []

        unique = []
        seen = set()

        for e in entities:

            if not isinstance(e, str):
                continue

            normalized = e.lower().strip()

            if normalized in seen:
                continue

            seen.add(normalized)
            unique.append(e)

        return unique