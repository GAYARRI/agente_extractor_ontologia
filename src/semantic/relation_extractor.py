import re


class RelationExtractor:

    def __init__(self):

        self.patterns = [

            ("located_in", r"(.*?) en ([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)"),

            ("occurs_in", r"(Festival|Fiesta|Carnaval|Romería).* de ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)"),

            ("near", r"(.*?) cerca de ([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)")
        ]


    def extract(self, text):

        relations = []

        for rel, pattern in self.patterns:

            matches = re.findall(pattern, text)

            for m in matches:

                if isinstance(m, tuple):

                    subj = m[0].strip()
                    obj = m[1].strip()

                else:

                    parts = m.split(" de ")

                    if len(parts) != 2:
                        continue

                    subj = parts[0]
                    obj = parts[1]

                relations.append({
                    "subject": subj,
                    "relation": rel,
                    "object": obj
                })

        return relations