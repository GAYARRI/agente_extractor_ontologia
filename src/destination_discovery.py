from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


class DestinationDiscovery:

    def __init__(self, model):

        self.model = model


    def discover(self, entities):

        names = [e["entity"] for e in entities]

        if not names:
            return []

        embeddings = self.model.encode(names)

        clustering = DBSCAN(
            eps=0.35,
            min_samples=2,
            metric="cosine"
        ).fit(embeddings)

        labels = clustering.labels_

        clusters = {}

        for i, label in enumerate(labels):

            if label == -1:
                continue

            clusters.setdefault(label, []).append(names[i])

        destinations = []

        for c in clusters.values():

            # usar el nombre más largo como representante
            representative = max(c, key=len)

            destinations.append(representative)

        return destinations