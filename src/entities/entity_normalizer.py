from __future__ import annotations
import os

from sentence_transformers import SentenceTransformer
import numpy as np

# 🔥 SAFE IMPORT (won’t break if module not present yet)
try:
    from entity_processing.name_cleaner import clean_entity_name
except Exception:
    def clean_entity_name(x):
        return x


class EntityNormalizer:

    def __init__(self):
        LOCAL_MODEL = r"C:\hf_models\paraphrase-multilingual-MiniLM-L12-v2"
        REMOTE_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

        if os.path.exists(LOCAL_MODEL):
            print("[DEBUG] Cargando modelo local")
            self.model = SentenceTransformer(LOCAL_MODEL)
        else:
            print("[DEBUG] Cargando modelo desde HuggingFace")
            self.model = SentenceTransformer(REMOTE_MODEL)

        self.threshold = 0.86

    def cosine(self, a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    def _entity_name(self, entity):
        """
        Extract and CLEAN entity name.
        This is the key improvement.
        """
        if isinstance(entity, dict):
            name = (
                entity.get("name")
                or entity.get("entity_name")
                or entity.get("entity")
                or entity.get("label")
                or ""
            ).strip()
        else:
            name = str(entity).strip()

        # 🔥 NEW: clean noisy names
        try:
            name = clean_entity_name(name)
        except Exception:
            pass

        return name

    def _entity_score(self, entity):
        if not isinstance(entity, dict):
            return 0.0

        for key in ("final_score", "score", "semantic_score", "semantic_similarity"):
            value = entity.get(key)
            try:
                if value is not None:
                    return float(value)
            except Exception:
                pass

        return 0.0

    def _entity_weight(self, entity):
        """
        Prefer the most informative entity in a cluster.
        """
        if not isinstance(entity, dict):
            return len(str(entity).strip())

        weight = 0

        name = self._entity_name(entity)
        weight += len(name)

        for field in (
            "description",
            "short_description",
            "long_description",
            "address",
            "phone",
            "email",
        ):
            value = entity.get(field)
            if isinstance(value, str) and value.strip():
                weight += 10

        props = entity.get("properties")
        if isinstance(props, dict):
            weight += len(
                [k for k, v in props.items() if v not in (None, "", [], {})]
            )

        return weight

    def _choose_best_representative(self, cluster_indices, entities):
        best_idx = cluster_indices[0]
        best_score = self._entity_score(entities[best_idx])
        best_weight = self._entity_weight(entities[best_idx])

        for idx in cluster_indices[1:]:
            score = self._entity_score(entities[idx])
            weight = self._entity_weight(entities[idx])

            if score > best_score:
                best_idx = idx
                best_score = score
                best_weight = weight
                continue

            if score == best_score and weight > best_weight:
                best_idx = idx
                best_weight = weight

        return best_idx

    def normalize(self, entities):
        """
        Cluster similar entities using embeddings and keep best representative.
        """
        if not entities:
            return entities

        names = [self._entity_name(e) for e in entities]

        valid_pairs = [
            (i, name) for i, name in enumerate(names)
            if name
        ]

        if not valid_pairs:
            return []

        valid_indices = [i for i, _ in valid_pairs]
        valid_names = [name for _, name in valid_pairs]

        embeddings = self.model.encode(valid_names)

        clusters = []

        for local_i, global_i in enumerate(valid_indices):
            placed = False

            for cluster in clusters:
                rep_local_index = cluster[0]

                sim = self.cosine(
                    embeddings[local_i],
                    embeddings[rep_local_index]
                )

                if sim > self.threshold:
                    cluster.append(local_i)
                    placed = True
                    break

            if not placed:
                clusters.append([local_i])

        normalized = []

        for cluster in clusters:
            global_cluster_indices = [
                valid_indices[local_idx] for local_idx in cluster
            ]
            best_global_idx = self._choose_best_representative(
                global_cluster_indices,
                entities
            )
            normalized.append(entities[best_global_idx])

        return normalized