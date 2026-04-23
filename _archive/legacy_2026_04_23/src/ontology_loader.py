from pathlib import Path
from rdflib import Graph, URIRef, RDF, RDFS, OWL
from rdflib.namespace import SKOS


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
    # Helpers
    # --------------------------------------------------

    def _local_name(self, uri):
        name = str(uri)
        if "#" in name:
            return name.split("#")[-1]
        return name.split("/")[-1]

    def _is_valid_name(self, name):
        return bool(name) and not name.startswith("N")

    # --------------------------------------------------
    # CLASES
    # --------------------------------------------------

    def get_classes(self):
        classes = []

        for s in self.graph.subjects(RDF.type, OWL.Class):
            if isinstance(s, URIRef):
                name = self._local_name(s)
                if self._is_valid_name(name):
                    classes.append(name)

        # Algunas ontologías usan rdfs:Class en vez de owl:Class
        for s in self.graph.subjects(RDF.type, RDFS.Class):
            if isinstance(s, URIRef):
                name = self._local_name(s)
                if self._is_valid_name(name):
                    classes.append(name)

        classes = sorted(set(classes))
        return classes

    # --------------------------------------------------
    # PROPIEDADES
    # --------------------------------------------------

    def get_properties(self):
        properties = []

        property_types = [
            RDF.Property,
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            OWL.AnnotationProperty,
        ]

        for ptype in property_types:
            for s in self.graph.subjects(RDF.type, ptype):
                if isinstance(s, URIRef):
                    name = self._local_name(s)
                    if self._is_valid_name(name):
                        properties.append(name)

        properties = sorted(set(properties))
        return properties

    # --------------------------------------------------
    # LABELS
    # --------------------------------------------------

    def get_labels(self):
        labels = {}

        for s, _, o in self.graph.triples((None, RDFS.label, None)):
            if isinstance(s, URIRef):
                name = self._local_name(s)
                if self._is_valid_name(name):
                    labels.setdefault(name, []).append(str(o))

        return labels

    # --------------------------------------------------
    # COMMENTS
    # --------------------------------------------------

    def get_comments(self):
        comments = {}

        for s, _, o in self.graph.triples((None, RDFS.comment, None)):
            if isinstance(s, URIRef):
                name = self._local_name(s)
                if self._is_valid_name(name):
                    comments.setdefault(name, []).append(str(o))

        return comments

    # --------------------------------------------------
    # ALIASES / SYNONYMS
    # --------------------------------------------------

    def get_aliases(self):
        aliases = {}

        alias_predicates = [
            SKOS.altLabel,
        ]

        for predicate in alias_predicates:
            for s, _, o in self.graph.triples((None, predicate, None)):
                if isinstance(s, URIRef):
                    name = self._local_name(s)
                    if self._is_valid_name(name):
                        aliases.setdefault(name, []).append(str(o))

        return aliases

    # --------------------------------------------------
    # DOMINIO / RANGO
    # --------------------------------------------------

    def get_property_schema(self):
        schema = {}

        property_types = [
            RDF.Property,
            OWL.ObjectProperty,
            OWL.DatatypeProperty,
            OWL.AnnotationProperty,
        ]

        properties = set()
        for ptype in property_types:
            for s in self.graph.subjects(RDF.type, ptype):
                if isinstance(s, URIRef):
                    pname = self._local_name(s)
                    if self._is_valid_name(pname):
                        properties.add((s, pname))

        for prop_uri, prop_name in properties:
            domains = []
            ranges = []

            for _, _, d in self.graph.triples((prop_uri, RDFS.domain, None)):
                if isinstance(d, URIRef):
                    domains.append(self._local_name(d))

            for _, _, r in self.graph.triples((prop_uri, RDFS.range, None)):
                if isinstance(r, URIRef):
                    ranges.append(self._local_name(r))

            schema[prop_name] = {
                "domains": sorted(set(domains)),
                "ranges": sorted(set(ranges)),
            }

        return schema

    # --------------------------------------------------
    # LOAD ESTRUCTURADO
    # --------------------------------------------------

    def load(self):
        classes = self.get_classes()
        properties = self.get_properties()
        labels = self.get_labels()
        comments = self.get_comments()
        aliases = self.get_aliases()
        property_schema = self.get_property_schema()

        class_dict = {}

        for cls in classes:
            class_dict[cls] = {
                "label": labels.get(cls, [cls])[0],
                "description": comments.get(cls, [""])[0],
                "aliases": aliases.get(cls, []),
            }

        property_dict = {}

        for prop in properties:
            property_dict[prop] = {
                "label": labels.get(prop, [prop])[0],
                "description": comments.get(prop, [""])[0],
                "aliases": aliases.get(prop, []),
                "domains": property_schema.get(prop, {}).get("domains", []),
                "ranges": property_schema.get(prop, {}).get("ranges", []),
            }

        print("\nClases ontológicas cargadas:\n")
        print(sorted(class_dict.keys()))

        print("\nPropiedades ontológicas cargadas:\n")
        print(sorted(property_dict.keys()))

        return {
            "classes": class_dict,
            "properties": property_dict,
        }

   