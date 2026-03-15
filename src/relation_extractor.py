import re


class RelationExtractor:

    def extract(self, entities, text):

        relations = []

        for e1 in entities:
            for e2 in entities:

                if e1 == e2:
                    continue

                # located in
                if re.search(rf"{e1}.*en {e2}", text, re.IGNORECASE):
                    relations.append((e1, "locatedIn", e2))

                # near
                if re.search(rf"{e1}.*cerca de {e2}", text, re.IGNORECASE):
                    relations.append((e1, "near", e2))

                # part of
                if re.search(rf"{e1}.*parte de {e2}", text, re.IGNORECASE):
                    relations.append((e1, "partOf", e2))

        return relations