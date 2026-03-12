from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef
from rdflib.namespace import XSD
import re


class RDFBuilder:
    """
    Construye el grafo RDF del Knowledge Graph turístico.
    Separa claramente:
        - clases ontológicas
        - propiedades
        - instancias
    """

    def __init__(self):
        self.graph = Graph()

        # Namespaces
        self.ONTO = Namespace("http://tourismkg.com/ontology/")
        self.RES = Namespace("http://tourismkg.com/resource/")
        self.PROV = Namespace("http://tourismkg.com/provenance/")

        # Bind prefixes
        self.graph.bind("onto", self.ONTO)
        self.graph.bind("res", self.RES)
        self.graph.bind("prov", self.PROV)
        self.graph.bind("rdfs", RDFS)

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    def _normalize_uri(self, text: str) -> str:
        """Convierte texto en identificador URI-safe"""
        text = text.strip().lower()
        text = re.sub(r"\s+", "_", text)
        text = re.sub(r"[^\w_]", "", text)
        return text

    def _entity_uri(self, name: str):
        return self.RES[self._normalize_uri(name)]

    def _class_uri(self, class_name: str):
        return self.ONTO[self._normalize_uri(class_name)]

    def _property_uri(self, prop_name: str):
        return self.ONTO[self._normalize_uri(prop_name)]

    # -------------------------------------------------
    # Instancias
    # -------------------------------------------------

    def add_instance(self, entity_name: str, ont_class: str, label=None):
        """
        Crea una instancia tipada.
        """

        entity_uri = self._entity_uri(entity_name)
        class_uri = self._class_uri(ont_class)

        self.graph.add((entity_uri, RDF.type, class_uri))

        if label:
            self.graph.add((entity_uri, RDFS.label, Literal(label)))

        return entity_uri

    # -------------------------------------------------
    # Propiedades de datos
    # -------------------------------------------------

    def add_data_property(self, subject, prop_name, value, datatype=None, lang=None):
        """
        Añade propiedad literal.
        """

        prop_uri = self._property_uri(prop_name)

        if datatype:
            literal = Literal(value, datatype=datatype)
        elif lang:
            literal = Literal(value, lang=lang)
        else:
            literal = Literal(value)

        self.graph.add((subject, prop_uri, literal))

    # -------------------------------------------------
    # Propiedades objeto
    # -------------------------------------------------

    def add_object_property(self, subject, prop_name, obj):
        """
        Añade relación entre entidades.
        """

        prop_uri = self._property_uri(prop_name)

        if isinstance(obj, str):
            obj = self._entity_uri(obj)

        self.graph.add((subject, prop_uri, obj))

    # -------------------------------------------------
    # Metadatos de extracción
    # -------------------------------------------------

    def add_provenance(self, subject, source_url=None, confidence=None, extractor=None):
        """
        Guarda metadatos de extracción.
        """

        if source_url:
            self.graph.add(
                (subject, self.PROV.source, Literal(source_url))
            )

        if confidence:
            self.graph.add(
                (subject, self.PROV.confidence, Literal(confidence, datatype=XSD.float))
            )

        if extractor:
            self.graph.add(
                (subject, self.PROV.extractor, Literal(extractor))
            )

    # -------------------------------------------------
    # Serialización
    # -------------------------------------------------

    def save(self, path="knowledge_graph.ttl"):
        self.graph.serialize(path, format="turtle")
        print(f"Knowledge Graph guardado en {path}")

    def size(self):
        return len(self.graph)