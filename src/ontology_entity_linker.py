from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class OntologyEntityLinker:

    def __init__(self, ontology_classes):

        print("Cargando modelo de embeddings...")

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.ontology_classes = ontology_classes

        print("Generando embeddings de clases ontológicas...")

        self.class_embeddings = self.model.encode(self.ontology_classes)


    def classify(self, entity):

        entity_embedding = self.model.encode([entity])

        similarity = cosine_similarity(
            entity_embedding,
            self.class_embeddings
        )

        best_index = similarity.argmax()

        return self.ontology_classes[best_index]


    def link(self, entities):

        results = []

        for entity in entities:

            ont_class = self.classify(entity)

            results.append({
                "name": entity,
                "class": ont_class
            })

        return results