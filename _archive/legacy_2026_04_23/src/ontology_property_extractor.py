from rdflib import Graph, RDF, RDFS, OWL


class OntologyLoader:

    def __init__(self, ontology_path):

        self.graph = Graph()
        self.graph.parse(ontology_path)

    # ------------------------------

    def get_classes(self):

        classes = []

        for s in self.graph.subjects(RDF.type, OWL.Class):

            name = s.split("#")[-1]

            classes.append(name)

        return classes

    # ------------------------------

    def get_properties(self):

        properties = []

        for s in self.graph.subjects(RDF.type, OWL.ObjectProperty):

            name = s.split("#")[-1]

            properties.append(name)

        for s in self.graph.subjects(RDF.type, OWL.DatatypeProperty):

            name = s.split("#")[-1]

            properties.append(name)

        return properties