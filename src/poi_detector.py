import re


POI_PATTERNS = [
    r"Playa de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"Castillo de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"Museo [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"Iglesia de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"Parque Natural de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+"
]


class POIDetector:

    def detect(self, text):

        pois = set()

        for pattern in POI_PATTERNS:

            matches = re.findall(pattern, text)

            for m in matches:
                pois.add(m.strip())

        return list(pois)