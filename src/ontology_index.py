import rdflib
from rdflib import Graph, URIRef, RDFS
from sentence_transformers import SentenceTransformer
import os


class OntologyIndex:

    def __init__(self, ontology_path):

        self.graph = rdflib.Graph()
        self.graph.parse(ontology_path)

        ontology_path = os.path.abspath(ontology_path)

        self.graph.parse(ontology_path)

        self.model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        self.classes={}
        self.properties={} 

        self.labels = []
        self.uris = []

        self.class_properties = {}

        self._index_classes()
        self._index_properties()

        self.embeddings = self.model.encode(self.labels)


    # ---------------------------------
    # indexar clases ontológicas
    # ---------------------------------

    def _index_classes(self):

        for s in self.graph.subjects():

            if "core#" not in str(s):
                continue

            uri = str(s)

            label = uri.split("#")[-1]

            if label not in self.labels:

                self.labels.append(label)
                self.uris.append(uri)


    # ---------------------------------
    # indexar propiedades ontológicas
    # ---------------------------------

    def _index_properties(self):

        for prop in self.graph.subjects(RDFS.domain, None):

            domain = self.graph.value(prop, RDFS.domain)
            range_ = self.graph.value(prop, RDFS.range)

            if not domain:
                continue

            domain_uri = str(domain)

            prop_uri = str(prop)

            self.class_properties.setdefault(domain_uri, []).append({
                "property": prop_uri,
                "range": str(range_) if range_ else None
            })


    # ---------------------------------
    # obtener propiedades de una clase
    # ---------------------------------

    def get_class_properties(self, class_uri):

        return self.class_properties.get(class_uri, [])


    # ---------------------------------
    # obtener jerarquía ontológica
    # ---------------------------------

    def get_hierarchy(self, class_uri):

        parents = []

        for s, p, o in self.graph.triples((URIRef(class_uri), RDFS.subClassOf, None)):

            parents.append(str(o))

        return parents


    # ---------------------------------
    # obtener etiqueta de clase
    # ---------------------------------

    def get_label(self, uri):

        return uri.split("#")[-1]
    
    def get_class_uri(self, class_name):

        for uri, data in self.classes.items():

            label = data.get("label", "").lower()

            if label == class_name.lower():
                return uri

        return None