from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


# clases raíz válidas de la ontología
VALID_ROOT_CLASSES = [
    "TouristResource",
    "Accommodation",
    "CulturalFacility",
    "NaturalResource"
]


# clases que suelen producir errores
INVALID_MATCHES = [
    "BullRing"
]


# pistas léxicas turísticas (muy importantes para mejorar precisión)
LEXICAL_HINTS = {
    "playa": "Beach",
    "castillo": "Castle",
    "iglesia": "Church",
    "catedral": "Church",
    "museo": "Museum",
    "festival": "Event",
    "romería": "Event",
    "carnaval": "Event",
    "parque": "Park",
    "ruta": "TouristRoute",
    "gastronom": "GastronomicResource"
}


class OntologyMatcher:

    def __init__(self, ontology_index):

        self.index = ontology_index
        self.model = ontology_index.model


    def match(self, entity):

        text = entity.lower()

        # 1️⃣ reglas léxicas (más rápidas y más precisas en turismo)
        for keyword, cls in LEXICAL_HINTS.items():

            if keyword in text:

                return {
                    "label": cls,
                    "uri": f"https://ontologia.segittur.es/turismo/def/core#{cls}",
                    "score": 0.90,
                    "fallback": True
                }

        # 2️⃣ generar embedding de la entidad
        vec = self.model.encode([entity])

        # 3️⃣ calcular similitud con clases ontológicas
        scores = cosine_similarity(
            vec,
            self.index.embeddings
        )

        idx = scores.argmax()

        uri = self.index.uris[idx]
        label = self.index.labels[idx]

        score = float(scores[0][idx])

        # 4️⃣ evitar matches incorrectos
        if any(x in label for x in INVALID_MATCHES) and score < 0.7:

            hierarchy = self.index.get_hierarchy(uri)

            if hierarchy:
                uri = hierarchy[0]
                label = uri.split("/")[-1]

        # 5️⃣ fallback jerárquico si score bajo
        hierarchy = self.index.get_hierarchy(uri)

        if score < 0.6 and hierarchy:

            for parent in hierarchy:

                parent_label = parent.split("/")[-1]

                if parent_label in VALID_ROOT_CLASSES:

                    return {
                        "label": parent_label,
                        "uri": parent,
                        "score": score,
                        "fallback": True
                    }

        # 6️⃣ resultado final
        return {
            "label": label,
            "uri": uri,
            "score": score,
            "fallback": False
        }