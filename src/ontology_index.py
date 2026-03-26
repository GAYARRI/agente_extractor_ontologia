import os
import rdflib
from rdflib import Graph, URIRef, RDFS, RDF
from rdflib.namespace import OWL
from sentence_transformers import SentenceTransformer


class OntologyIndex:
    def __init__(self, ontology_path):
        ontology_path = os.path.abspath(ontology_path)

        self.graph = Graph()
        self.graph.parse(ontology_path)

        self.model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        self.classes = {}
        self.properties = {}

        self.labels = []
        self.uris = []

        self.class_properties = {}

        self._index_classes()
        self._index_properties()

        if self.labels:
            self.embeddings = self.model.encode(self.labels)
        else:
            self.embeddings = []

    # ---------------------------------
    # indexar clases ontológicas reales
    # ---------------------------------
    def _index_classes(self):
        found = set()

        # owl:Class
        for s in self.graph.subjects(RDF.type, OWL.Class):
            found.add(s)

        # rdfs:Class
        for s in self.graph.subjects(RDF.type, RDFS.Class):
            found.add(s)

        for s in found:
            uri = str(s)
            label = self._extract_label(s)

            self.classes[uri] = {
                "uri": uri,
                "label": label,
            }

            self.labels.append(label)
            self.uris.append(uri)

        if not self.classes:
            print("⚠ No se encontraron clases ontológicas")
        else:
            print(f"✅ Clases ontológicas indexadas: {len(self.classes)}")

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
    # extraer etiqueta legible
    # ---------------------------------
    def _extract_label(self, resource):
        label = self.graph.value(resource, RDFS.label)

        if label:
            return str(label)

        uri = str(resource)

        if "#" in uri:
            return uri.split("#")[-1]

        return uri.rstrip("/").split("/")[-1]

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

        for _, _, o in self.graph.triples((URIRef(class_uri), RDFS.subClassOf, None)):
            parents.append(str(o))

        return parents

    # ---------------------------------
    # obtener etiqueta de clase
    # ---------------------------------
    def get_label(self, uri):
        if uri in self.classes:
            return self.classes[uri]["label"]

        if "#" in uri:
            return uri.split("#")[-1]

        return uri.rstrip("/").split("/")[-1]

    # ---------------------------------
    # obtener URI a partir del nombre
    # ---------------------------------
    def get_class_uri(self, class_name):
        if not class_name:
            return None

        class_name = class_name.lower().strip()

        for uri, data in self.classes.items():
            label = data.get("label", "").lower().strip()
            if label == class_name:
                return uri

        return None