from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class OntologyMatcher:

    def __init__(self, ontology_index):

        self.index = ontology_index
        self.model = ontology_index.model

        # número de candidatos semánticos a evaluar
        self.top_k = 5

        # score mínimo razonable
        self.min_score = 0.65


    # -----------------------------------
    # comprobar si la clase es ontológica
    # relevante (según jerarquía)
    # -----------------------------------

    def _is_valid_class(self, uri):

        hierarchy = self.index.get_hierarchy(uri)

        # si no tiene jerarquía probablemente
        # sea clase técnica o aislada
        if not hierarchy:
            return False

        return True


    # -----------------------------------
    # matching semántico
    # -----------------------------------

    def match(self, entity):

        vec = self.model.encode([entity])

        scores = cosine_similarity(
            vec,
            self.index.embeddings
        )

        scores = scores[0]

        # obtener top-k candidatos
        top_indices = np.argsort(scores)[-self.top_k:][::-1]

        for idx in top_indices:

            uri = self.index.uris[idx]
            label = self.index.labels[idx]
            if len(label) < 4:
                continue
            score = float(scores[idx])

            # descartar matches débiles
            if score < self.min_score:
                continue

            # validar ontológicamente
            if not self._is_valid_class(uri):
                continue

            return {
                "label": label,
                "uri": uri,
                "score": score
            }

        return None