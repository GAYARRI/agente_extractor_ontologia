import re
from sklearn.metrics.pairwise import cosine_similarity


POI_PATTERNS = [

    r"Castillo de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"Museo de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"Iglesia de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"Parque Natural de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"Ruta de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
    r"Playa de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",

]


class POIDetector:

    def __init__(self, model):

        self.model = model

        self.poi_types = [
            "castle",
            "museum",
            "church",
            "beach",
            "natural park",
            "tourist route"
        ]

        self.poi_embeddings = model.encode(self.poi_types)


    def detect_patterns(self, text):

        pois = []

        for pattern in POI_PATTERNS:

            matches = re.findall(pattern, text)

            for m in matches:

                pois.append(m.strip())

        return pois


    def detect_semantic(self, entity):

        vec = self.model.encode([entity])

        scores = cosine_similarity(vec, self.poi_embeddings)

        score = scores.max()

        if score > 0.65:

            return True

        return False