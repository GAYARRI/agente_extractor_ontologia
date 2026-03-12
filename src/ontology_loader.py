from rdflib import Graph, URIRef, RDF, RDFS, OWL
from pathlib import Path


class OntologyLoader:

    def __init__(self, ontology_path):

        print("Cargando ontología:", ontology_path)

        self.graph = Graph()

        path = Path(ontology_path)

        if not path.exists():
            raise FileNotFoundError(f"Ontología no encontrada: {ontology_path}")

        try:
            self.graph.parse(path, format="xml")
        except Exception:
            self.graph.parse(path, format="turtle")

        print("Triples cargados:", len(self.graph))


    # --------------------------------------------------
    # CLASES
    # --------------------------------------------------

    def get_classes(self):

        classes = []

        for s in self.graph.subjects(RDF.type, OWL.Class):

            if isinstance(s, URIRef):

                name = str(s)

                if "#" in name:
                    name = name.split("#")[-1]
                else:
                    name = name.split("/")[-1]

                if name and not name.startswith("N"):
                    classes.append(name)

        classes = sorted(list(set(classes)))

        print("\nClases ontológicas cargadas:\n")
        print(classes)

        return classes


    # --------------------------------------------------
    # PROPIEDADES
    # --------------------------------------------------

    def get_properties(self):

        properties = []

        for s in self.graph.subjects(RDF.type, RDF.Property):

            if isinstance(s, URIRef):

                name = str(s)

                if "#" in name:
                    name = name.split("#")[-1]
                else:
                    name = name.split("/")[-1]

                if name and not name.startswith("N"):
                    properties.append(name)

        properties = sorted(list(set(properties)))

        print("\nPropiedades ontológicas cargadas:\n")
        print(properties)

        return properties


    # --------------------------------------------------
    # LABELS
    # --------------------------------------------------

    def get_class_labels(self):

        labels = {}

        for s, p, o in self.graph.triples((None, RDFS.label, None)):

            name = str(s)

            if "#" in name:
                name = name.split("#")[-1]
            else:
                name = name.split("/")[-1]

            labels[name] = str(o)

        return labels


    # --------------------------------------------------
    # COMMENTS
    # --------------------------------------------------

    def get_class_comments(self):

        comments = {}

        for s, p, o in self.graph.triples((None, RDFS.comment, None)):

            name = str(s)

            if "#" in name:
                name = name.split("#")[-1]
            else:
                name = name.split("/")[-1]

            comments[name] = str(o)

        return comments


   