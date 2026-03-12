import re


class TourismEntityDetector:

    def __init__(self):

        # patrones típicos de entidades turísticas
        self.patterns = [

            r"(Museo\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)",
            r"(Catedral\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)",
            r"(Iglesia\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)",
            r"(Palacio\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)",
            r"(Castillo\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)",
            r"(Parque\s+(?:Nacional|Natural)\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)",
            r"(Playa\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)",
            r"(Ruta\s+de\s+(?:la|las|los)?\s*[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)",
            r"(Monasterio\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)",
            r"(Basílica\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)",
            r"(Parque\s+de\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)",
        ]


    def detect(self, text):

        entities = []

        for pattern in self.patterns:

            matches = re.findall(pattern, text)

            for match in matches:

                entities.append({
                    "name": match.strip(),
                    "type": "TouristAttraction"
                })

        # eliminar duplicados
        unique = {}
        for e in entities:
            unique[e["name"]] = e

        return list(unique.values())