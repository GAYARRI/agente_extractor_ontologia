from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class EmbeddingEntityLinker:

    def __init__(self):

        print("Cargando modelo de embeddings...")

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        # Clases de la ontología (puedes ampliarlas)
        self.ontology_classes = [
            "Beach",
            "Museum",
            "Hotel",
            "Restaurant",
            "Bar",
            "CafeOrCoffeeShop",
            "TouristInformationOffice",
            "Theater",
            "Monument",
            "NaturalResource",
            "Mountain",
            "Volcano",
            "TourismDestination",
            "TourismOrganisation",
            "Event",
            "EventAttendanceFacility",
            "Place"
        ]

        print("Generando embeddings de clases...")

        self.class_embeddings = self.model.encode(self.ontology_classes)

    def link(self, entities):

        results = []

        for entity in entities:

            entity_embedding = self.model.encode([entity])

            similarity = cosine_similarity(entity_embedding, self.class_embeddings)

            best_index = similarity.argmax()

            best_class = self.ontology_classes[best_index]

            results.append({
                "name": entity,
                "class": best_class
            })

        return results