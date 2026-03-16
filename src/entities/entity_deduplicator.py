class EntityDeduplicator:

    def deduplicate(self, entities):

        entities = list(set(entities))

        result = []

        for e in entities:

            contained = False

            for other in entities:

                if e != other and e in other:
                    contained = True
                    break

            if not contained:
                result.append(e)

        return result