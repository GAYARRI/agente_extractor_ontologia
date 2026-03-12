import re


class TourismRelationExtractor:

    def __init__(self):

        # patrones típicos de relación
        self.patterns = [

            r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)\s+(?:se encuentra en|está en|situado en|ubicado en)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)",

            r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)\s+en\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)",

            r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)\s+de\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)"
        ]


    def extract(self, text):

        relations = []

        for pattern in self.patterns:

            matches = re.findall(pattern, text)

            for match in matches:

                entity1 = match[0].strip()
                entity2 = match[1].strip()

                relations.append({
                    "subject": entity1,
                    "predicate": "locatedIn",
                    "object": entity2
                })

        # eliminar duplicados
        unique = []

        seen = set()

        for r in relations:

            key = (r["subject"], r["object"])

            if key not in seen:
                seen.add(key)
                unique.append(r)

        return {"relations": unique}