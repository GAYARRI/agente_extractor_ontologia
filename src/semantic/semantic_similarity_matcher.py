from sentence_transformers import SentenceTransformer
import numpy as np


class SemanticSimilarityMatcher:

    def __init__(self, ontology_index):

        self.ontology_index = ontology_index

        # modelo semántico
        self.model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        # clases de la ontología
        self.classes = list(self.ontology_index.classes.keys())

        if not self.classes:
            print("⚠ No se encontraron clases ontológicas")
            self.class_embeddings = []
            return

        # embeddings de clases
        self.class_embeddings = self.model.encode(self.classes)

    # ---------------------------------------------------
    # similitud coseno
    # ---------------------------------------------------

    def cosine(self, a, b):

        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    # ---------------------------------------------------
    # matching semántico
    # ---------------------------------------------------

    def match(self, text):

        if not self.classes:
            return None

        try:

            emb = self.model.encode([text])[0]

        except Exception as e:

            print("Error generando embedding:", e)
            return None

        best_score = 0
        best_class = None

        for i, c in enumerate(self.classes):

            score = self.cosine(
                emb,
                self.class_embeddings[i]
            )

            if score > best_score:

                best_score = score
                best_class = c

        if best_class is None:
            return None

        return {
            "label": best_class,
            "score": float(best_score)
        }