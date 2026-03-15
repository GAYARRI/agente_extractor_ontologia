from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS
from urllib.parse import quote


MIN_CONFIDENCE = 0.75


class KnowledgeGraphBuilder:

    def __init__(self, ontology_index, source_page=None):

        self.graph = Graph()

        self.EX = Namespace("http://example.org/resource/")
        self.TOUR = Namespace("http://example.org/tourism/")

        self.graph.bind("ex", self.EX)
        self.graph.bind("tour", self.TOUR)
        self.graph.bind("rdfs", RDFS)

        self.source_page = source_page
        self.ontology_index = ontology_index

        # evitar duplicados
        self.seen_entities = set()


    def _create_uri(self, label):
        """
        Crear URI limpia para la entidad
        """

        clean_label = label.strip().replace(" ", "_")
        clean_label = quote(clean_label)

        return self.EX[clean_label]


    def _create_class_uri(self, class_label):
        """
        Obtener URI real de la ontología
        """

        for uri, label in zip(
            self.ontology_index.uris,
            self.ontology_index.labels
        ):

            # label puede contener contexto, tomamos el nombre base
            base_label = label.split(" ")[0]

            if base_label.lower() == class_label.lower():
                return URIRef(uri)

        # fallback si no se encuentra
        clean_class = quote(class_label.replace(" ", "_"))
        return self.TOUR[clean_class]


    def add_results(self, results):

        for block in results:

            for e in block["entities"]:

                entity_label = e["entity"].strip()
                class_label = e["class"]
                score = float(e["score"])

                # filtrar baja confianza
                if score < MIN_CONFIDENCE:
                    continue

                key = entity_label.lower()

                # evitar duplicados
                if key in self.seen_entities:
                    continue

                self.seen_entities.add(key)

                subject = self._create_uri(entity_label)
                class_uri = self._create_class_uri(class_label)

                # tipo RDF
                self.graph.add((subject, RDF.type, class_uri))

                # etiqueta
                self.graph.add((subject, RDFS.label, Literal(entity_label)))

                # confianza
                self.graph.add(
                    (subject, self.TOUR.confidence, Literal(score))
                )

                # página fuente
                if self.source_page:

                    self.graph.add(
                        (
                            subject,
                            self.TOUR.sourcePage,
                            Literal(self.source_page)
                        )
                    )


    def save(self, path="knowledge_graph.ttl"):

        self.graph.serialize(destination=path, format="turtle")