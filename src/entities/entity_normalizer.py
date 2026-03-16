from sentence_transformers import SentenceTransformer
import numpy as np


class EntityNormalizer:

    def __init__(self):

        self.model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        self.threshold = 0.82


    def cosine(self, a, b):

        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


    def normalize(self, entities):

        if not entities:
            return entities

        embeddings = self.model.encode(entities)

        clusters = []

        for i, entity in enumerate(entities):

            placed = False

            for cluster in clusters:

                rep_index = cluster[0]

                sim = self.cosine(
                    embeddings[i],
                    embeddings[rep_index]
                )

                if sim > self.threshold:

                    cluster.append(i)
                    placed = True
                    break

            if not placed:
                clusters.append([i])

        normalized = []

        for cluster in clusters:

            rep = entities[cluster[0]]

            normalized.append(rep)

        return normalized