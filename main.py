import os

from src.site_crawler import SiteCrawler
from src.ner_extractor import NERExtractor
from src.embedding_entity_linker import EmbeddingEntityLinker
from src.relation_extractor import RelationExtractor
from src.tourism_property_extractor import TourismPropertyExtractor
from src.rdf_builder import RDFBuilder
from src.ontology_entity_linker import OntologyEntityLinker
from src.ontology_loader import OntologyLoader



START_URL = "https://webtenerife.com"

BASE_URI = "http://tourismkg.com/entity/"


ONTOLOGY_PATH = "ontology/core.ttl" 


ontology = OntologyLoader(ONTOLOGY_PATH)

ontology_classes = ontology.get_classes()

ontology_properties = ontology.get_properties()

# -----------------------------
# Inicializar componentes
# -----------------------------

crawler = SiteCrawler(START_URL, max_pages=None)

ner = NERExtractor()

entity_linker = EmbeddingEntityLinker()

relation_extractor = RelationExtractor()

property_extractor = TourismPropertyExtractor()

builder = RDFBuilder(BASE_URI)


# almacenar entidades para markdown
all_entities = []


# -----------------------------
# CRAWL
# -----------------------------

pages = crawler.crawl_site()

print("\nNúmero de páginas encontradas:", len(pages))


# -----------------------------
# ANALIZAR PAGINAS
# -----------------------------

for page in pages:

    url = page["url"]
    html = page["html"]
    text = page["text"]

    print("\n==============================")
    print("Analizando página:", url)
    print("==============================")

    print("HTML length:", len(html))
    print("TEXT length:", len(text))

    # -----------------------------
    # NER
    # -----------------------------

    candidates = ner.extract(text)

    print("\nEntidades candidatas:\n")
    print(candidates)

    if not candidates:
        continue

    # -----------------------------
    # ENTITY LINKING
    # -----------------------------

    linked_entities = entity_linker.link(candidates)

    print("\nEntidades detectadas:\n")
    print(linked_entities)

    # -----------------------------
    # PROCESAR ENTIDADES
    # -----------------------------

    for entity in linked_entities:

        name = entity["name"]
        ont_class = entity["class"]

        uri = builder.create_uri(name)

        # guardar instancia RDF
        builder.add_instance(uri, ont_class)

        # -----------------------------
        # PROPIEDADES
        # -----------------------------

        properties = property_extractor.extract(html, text, url, name)

        if isinstance(properties, dict):

            builder.add_properties(uri, properties)

        elif isinstance(properties, list):

            for p in properties:

                if isinstance(p, dict):

                    predicate = p.get("property")
                    value = p.get("value")

                    if predicate and value:

                        builder.add_property(uri, predicate, value)

        # -----------------------------
        # almacenar entidad para markdown
        # -----------------------------

        entity_data = {
            "name": name,
            "class": ont_class,
            "properties": properties
        }

        all_entities.append(entity_data)

    # -----------------------------
    # RELACIONES
    # -----------------------------

    relations = relation_extractor.extract(text, linked_entities)

    if relations:

        for rel in relations:

            builder.add_relation(rel)


# -----------------------------
# GUARDAR RDF
# -----------------------------

builder.save("knowledge_graph.ttl")

print("\nKnowledge Graph guardado en knowledge_graph.ttl")


# -----------------------------
# GENERAR MARKDOWN
# -----------------------------

print("\nGenerando markdown de entidades...")

with open("entities.md", "w", encoding="utf-8") as f:

    f.write("# Tourism Knowledge Graph Entities\n\n")

    classes = {}

    for entity in all_entities:

        cls = entity["class"]

        if cls not in classes:
            classes[cls] = []

        classes[cls].append(entity)

    for cls, ents in classes.items():

        f.write(f"## {cls}\n\n")

        for e in ents:

            f.write(f"- **{e['name']}**\n")

            props = e["properties"]

            if isinstance(props, dict):

                for p, v in props.items():

                    f.write(f"  - {p}: {v}\n")

            elif isinstance(props, list):

                for p in props:

                    if isinstance(p, dict):

                        f.write(
                            f"  - {p.get('property')} : {p.get('value')}\n"
                        )

            f.write("\n")


print("Markdown generado: entities.md")