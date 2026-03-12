from rdflib import Graph, URIRef, Literal, RDF
import re
import urllib.parse


class RDFBuilder:

    def __init__(self, base_uri="http://tourismkg.com/entity/"):

        self.graph = Graph()

        self.base_uri = base_uri
        self.property_uri = "http://tourismkg.com/property/"

    # -----------------------------
    # añadir instancia
    # -----------------------------

    def add_instance(self, uri, ont_class):

        subject = URIRef(uri)

        class_uri = URIRef(self.property_uri + ont_class)

        self.graph.add((subject, RDF.type, class_uri))


    # -----------------------------
    # añadir propiedad
    # -----------------------------

    def add_property(self, uri, prop, value):

        subject = URIRef(uri)

        predicate = URIRef(self.property_uri + prop)

        self.graph.add((subject, predicate, Literal(value)))


    # -----------------------------
    # añadir propiedades
    # -----------------------------

    def add_properties(self, uri, properties):

        for p, v in properties.items():

            self.add_property(uri, p, v)


    # -----------------------------
    # añadir relación
    # -----------------------------

    def add_relation(self, relation):

        subject = URIRef(self.base_uri + relation["subject"].replace(" ", "_"))

        predicate = URIRef(self.property_uri + relation["predicate"])

        obj = URIRef(self.base_uri + relation["object"].replace(" ", "_"))

        self.graph.add((subject, predicate, obj))


    # -----------------------------
    # guardar grafo
    # -----------------------------

    def save(self, filename):

        self.graph.serialize(filename, format="turtle")
        

    def clean_uri(self,text):
    

        import re
        import urllib.parse

        # quitar comillas
        text = text.replace('"', "")

        # eliminar caracteres raros
        text = re.sub(r"[^\w\s-]", "", text)

        # espacios → _
        text = text.strip().replace(" ", "_")

        # codificar URI
        text = urllib.parse.quote(text)

        return text    

        
    
    def create_uri(self, name):
        import unicodedata
        

        name = unicodedata.normalize("NFKD", name)

        name = self.clean_uri(name)

        return self.base_uri + name