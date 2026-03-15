from sentence_transformers import SentenceTransformer
import numpy as np


class MultimodalEntityResolver:

    def __init__(self, candidate_classes):

        self.candidate_classes = candidate_classes

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.class_embeddings = self.model.encode(candidate_classes)


    def resolve(self, entity_text, description="", image_label=None, candidate_classes=None):

        text = f"{entity_text} {description}"

        text_embedding = self.model.encode([text])[0]

        scores = []

        for class_emb in self.class_embeddings:

            sim = np.dot(text_embedding, class_emb) / (
                np.linalg.norm(text_embedding) * np.linalg.norm(class_emb)
            )

            scores.append(sim)

        best_idx = int(np.argmax(scores))

        return self.candidate_classes[best_idx]