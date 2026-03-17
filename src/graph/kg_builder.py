from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS


class KnowledgeGraphBuilder:

    def __init__(self, ontology_index):

        self.graph = Graph()
        self.ontology_index = ontology_index

        self.EX = Namespace("http://example.org/resource/")
        self.TOUR = Namespace("http://example.org/tourism/")

        self.graph.bind("ex", self.EX)
        self.graph.bind("tour", self.TOUR)
        self.graph.bind("rdfs", RDFS)


    # ------------------------------------------------
    # construir KG desde resultados del pipeline
    # ------------------------------------------------

    def build(self, results):

        for block in results:

            for entity in block.get("entities", []):

                name = entity.get("entity")
                cls = entity.get("class")
                score = entity.get("score")

                if not name:
                    continue

                uri = URIRef(self.EX[name.replace(" ", "_")])

                # tipo
                if cls:
                    class_uri = URIRef(cls)
                    self.graph.add((uri, RDF.type, class_uri))

                # etiqueta
                self.graph.add((uri, RDFS.label, Literal(name)))

                # confianza
                if score is not None:
                    self.graph.add((uri, self.TOUR.confidence, Literal(score)))

                # 🔥 PROPIEDADES (AQUÍ dentro del loop)
                props = entity.get("properties", {})

                for k, v in props.items():
                    pred = self.TOUR[k]
                    self.graph.add((uri, pred, Literal(v)))

    # 🔥 ESTE MÉTODO FALTABA
    def save(self, path):
        self.graph.serialize(destination=path, format="turtle")                