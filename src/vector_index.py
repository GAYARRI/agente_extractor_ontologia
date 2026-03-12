from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class VectorIndex:

    def __init__(self):

        print("Cargando modelo de embeddings...")

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.entities = []
        self.embeddings = None


    # ----------------------------------------
    # CREAR INDICE
    # ----------------------------------------

    def build(self, entities):

        self.entities = entities

        texts = []

        for e in entities:

            texts.append(e["name"])

        self.embeddings = self.model.encode(texts)


    # ----------------------------------------
    # BUSQUEDA SEMANTICA
    # ----------------------------------------

    def search(self, query, top_k=5):

        query_embedding = self.model.encode([query])

        similarities = cosine_similarity(query_embedding, self.embeddings)

        idx = np.argsort(similarities[0])[::-1][:top_k]

        results = []

        for i in idx:

            results.append(self.entities[i])

        return results