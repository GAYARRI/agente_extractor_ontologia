from rdflib import Graph, RDF, OWL
from rdflib import RDF, OWL, URIRef


class OntologyLoader:

    def __init__(self, ontology_path):

        self.graph = Graph()

        # core.ttl realmente es RDF/XML
        self.graph.parse(ontology_path, format="xml")


    def get_classes(self):

         classes = []

         for s in self.graph.subjects(RDF.type, OWL.Class):

           if isinstance(s, URIRef):

             name = str(s).split("/")[-1].split("#")[-1]

             if not name.startswith("N"):
                classes.append(name)

         return sorted(set(classes))


    def get_properties(self):

        properties = []

        for s in self.graph.subjects(RDF.type, RDF.Property):

            name = str(s).split("/")[-1].split("#")[-1]
            properties.append(name)

        return properties