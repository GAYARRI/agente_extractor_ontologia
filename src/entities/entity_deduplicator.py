class EntityDeduplicator:

    def deduplicate(self, results):

        seen = {}
        clean_results = []

        for block in results:

            new_entities = []

            for e in block["entities"]:

                label = e["entity"].lower()

                if label in seen:
                    continue

                seen[label] = True

                new_entities.append(e)

            if new_entities:

                block["entities"] = new_entities
                clean_results.append(block)

        return clean_results