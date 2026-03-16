from sklearn.cluster import DBSCAN
import numpy as np


class DestinationDiscovery:

    def __init__(self, model):

        self.model = model

        # distancia semántica
        self.eps = 0.35

        # tamaño mínimo cluster
        self.min_samples = 2


    def discover(self, entities):

        if not entities:
            return []

        names = [e["entity"] for e in entities]

        embeddings = self.model.encode(names)

        clustering = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric="cosine"
        ).fit(embeddings)

        labels = clustering.labels_

        clusters = {}

        for label, name in zip(labels, names):

            if label == -1:
                continue

            clusters.setdefault(label, []).append(name)

        destinations = []

        for cluster in clusters.values():

            # elegimos el nombre más largo
            destination = max(cluster, key=len)

            destinations.append(destination)

        return list(set(destinations))