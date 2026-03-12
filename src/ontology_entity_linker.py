from sentence_transformers import SentenceTransformer
from rapidfuzz import fuzz
import numpy as np


class OntologyEntityLinker:
    """
    Clasifica entidades usando las clases de la ontología.
    Combina:
        - similitud semántica (embeddings)
        - similitud léxica
    """

    def __init__(self, ontology_classes):
        """
        ontology_classes debe ser un dict tipo:

        {
            "Hotel": {
                "label": "Hotel",
                "description": "Tourist accommodation establishment",
                "aliases": ["hotel", "resort", "hostel"]
            },
            ...
        }
        """

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.classes = ontology_classes
        self.class_names = list(ontology_classes.keys())

        # Construir textos de referencia
        self.class_texts = []
        for cname, data in ontology_classes.items():

            parts = [data.get("label", cname)]

            if data.get("description"):
                parts.append(data["description"])

            if data.get("aliases"):
                parts.extend(data["aliases"])

            self.class_texts.append(" ".join(parts))

        self.class_embeddings = self.model.encode(self.class_texts)

    def classify(self, entity_text):
        """
        Devuelve:
            clase ontológica
            score
        """

        entity_embedding = self.model.encode([entity_text])[0]

        # Similaridad semántica
        semantic_scores = np.dot(self.class_embeddings, entity_embedding)

        # Similaridad léxica
        lexical_scores = []
        for cname in self.class_names:
            lexical_scores.append(
                fuzz.token_set_ratio(entity_text.lower(), cname.lower()) / 100
            )

        lexical_scores = np.array(lexical_scores)

        # combinación híbrida
        scores = 0.7 * semantic_scores + 0.3 * lexical_scores

        best_idx = int(np.argmax(scores))

        return {
            "class": self.class_names[best_idx],
            "confidence": float(scores[best_idx])
        }