from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class EntityLinker:

    def __init__(self, ontology_classes):

        self.ontology_classes = ontology_classes

        print("Cargando modelo de embeddings...")

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        # embeddings de las clases
        self.class_embeddings = self.model.encode(ontology_classes)

    # -------------------------------------------------

    def classify(self, entity):

        entity_embedding = self.model.encode([entity])

        similarities = cosine_similarity(entity_embedding, self.class_embeddings)

        best_idx = np.argmax(similarities)

        best_class = self.ontology_classes[best_idx]

        score = similarities[0][best_idx]

        # umbral mínimo
        if score < 0.35:
            return "TourismEntity"

        return best_class

    # -------------------------------------------------

    def link(self, entities):

        linked = []

        for e in entities:

            ont_class = self.classify(e)

            linked.append({
                "name": e,
                "class": ont_class
            })

        return linked