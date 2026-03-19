from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class EntityClusterer:

    def __init__(self):
        self.model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

    # ==================================================
    # AGRUPAR ENTIDADES SIMILARES
    # ==================================================
    def cluster(self, entities):

        if not entities:
            return []

        names = [e["entity"] for e in entities]

        embeddings = self.model.encode(names)

        clusters = []
        used = set()

        for i, emb in enumerate(embeddings):

            if i in used:
                continue

            group = [i]
            used.add(i)

            for j in range(i + 1, len(embeddings)):

                if j in used:
                    continue

                sim = cosine_similarity([emb], [embeddings[j]])[0][0]

                if sim > 0.80:  # 🔥 threshold clave
                    group.append(j)
                    used.add(j)

            clusters.append(group)

        return clusters

    # ==================================================
    # FUSIONAR CLUSTERS
    # ==================================================
    def merge_clusters(self, entities):

        clusters = self.cluster(entities)

        merged_entities = []

        for group in clusters:

            best = None

            for idx in group:

                e = entities[idx]

                if not best or e["score"] > best["score"]:
                    best = e

            merged_entities.append(best)

        return merged_entities