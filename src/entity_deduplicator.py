from sentence_transformers import SentenceTransformer
import numpy as np


class EntityDeduplicator:

    def __init__(self, threshold=0.85):

        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

        self.threshold = threshold

        self.entities = []
        self.embeddings = []

    def cosine(self, a, b):

        return np.dot(a, b)

    def find_duplicate(self, entity):

        emb = self.model.encode(entity, normalize_embeddings=True)

        if not self.embeddings:

            return None, emb

        scores = np.dot(self.embeddings, emb)

        best_idx = np.argmax(scores)
        best_score = scores[best_idx]

        if best_score > self.threshold:

            return self.entities[best_idx], emb

        return None, emb

    def add(self, entity):

        duplicate, emb = self.find_duplicate(entity)

        if duplicate:

            return duplicate

        self.entities.append(entity)
        self.embeddings.append(emb)

        return entity