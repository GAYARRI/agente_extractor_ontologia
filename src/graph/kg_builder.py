from rdflib import Graph, Namespace, URIRef, Literal
import re


class KnowledgeGraphBuilder:

    def __init__(self, ontology_index=None):

        self.graph = Graph()

        # Namespaces
        self.EX = Namespace("http://example.org/resource/")
        self.TOUR = Namespace("http://example.org/tourism/")

        self.graph.bind("ex", self.EX)
        self.graph.bind("tour", self.TOUR)

        self.ontology_index = ontology_index

    # ==================================================
    # NORMALIZACIÓN DE ENTIDADES (CLAVE)
    # ==================================================

    def normalize_entity(self, label):

        if not label:
            return ""

        label = label.lower().strip()

        # quitar caracteres raros
        label = re.sub(r"[^\w\s]", "", label)

        # espacios → _
        label = label.replace(" ", "_")

        return label

    # ==================================================
    # BUILD DEL GRAFO
    # ==================================================

    def build(self, results):

        for block in results:

            entities = block.get("entities", [])

            for entity in entities:

                label = entity.get("entity")

                if not label:
                    continue

                # 🔥 SUBJECT NORMALIZADO (evita duplicados)
                normalized = self.normalize_entity(label)

                if not normalized:
                    continue

                subject = URIRef(self.EX[normalized])

                # -------------------------
                # TIPO
                # -------------------------

                entity_class = entity.get("class", "Place")

                self.graph.add((
                    subject,
                    self.TOUR.type,
                    Literal(entity_class)
                ))

                # -------------------------
                # PROPIEDADES
                # -------------------------

                props = entity.get("properties", {})

                for k, v in props.items():

                    if not k or not v:
                        continue

                    # normalizar propiedad
                    pred = self.TOUR[k.replace(" ", "_")]

                    self.graph.add((
                        subject,
                        pred,
                        Literal(v)
                    ))

                # -------------------------
                # DESCRIPCIONES (NUEVO 🔥)
                # -------------------------

                short_desc = entity.get("short_description")
                long_desc = entity.get("long_description")

                if short_desc:
                    self.graph.add((
                        subject,
                        self.TOUR.shortDescription,
                        Literal(short_desc)
                    ))

                if long_desc:
                    self.graph.add((
                        subject,
                        self.TOUR.longDescription,
                        Literal(long_desc)
                    ))

                # -------------------------
                # WIKIDATA LINK (si existe)
                # -------------------------

                wikidata_id = entity.get("wikidata_id")

                if wikidata_id:
                    wikidata_url = f"https://www.wikidata.org/wiki/{wikidata_id}"

                    self.graph.add((
                        subject,
                        self.TOUR.wikidata,
                        Literal(wikidata_url)
                    ))

    # ==================================================
    # GUARDAR
    # ==================================================

    def save(self, path):

        self.graph.serialize(destination=path, format="turtle")           