import time

from src.playwright_crawler import PlaywrightCrawler
from src.site_crawler import SiteCrawler

from src.html_block_extractor import HTMLBlockExtractor
from src.block_classifier import BlockClassifier

from src.multimodal_entity_resolver import MultimodalEntityResolver
from src.ontology_class_selector import OntologyDrivenClassSelector

from src.entity_cleaner import EntityCleaner
from src.entity_canonicalizer import EntityCanonicalizer

from src.relation_extractor import RelationExtractor
from src.wikidata_linker import WikidataLinker

from src.rdf_builder import RDFBuilder


SEED_URL = "https://turismo.maspalomas.com"


def main():

    start_time = time.time()

    print("\n=== INICIALIZANDO COMPONENTES ===\n")

    extractor = HTMLBlockExtractor()
    classifier = BlockClassifier()

    cleaner = EntityCleaner()
    canonicalizer = EntityCanonicalizer()

    relation_extractor = RelationExtractor()
    wikidata_linker = WikidataLinker()

    rdf_builder = RDFBuilder()

    # ontología
    class_selector = OntologyDrivenClassSelector("ontology/core.rdf")

    top_classes = [
        "place",
        "activity",
        "event",
        "hotel",
        "restaurant",
        "naturalarea"
    ]

    candidate_classes = class_selector.get_subclasses_multi(top_classes)

    entity_resolver = MultimodalEntityResolver(candidate_classes)

    print("\n=== CRAWLING ===\n")

    pages = []

    try:

        print("[INFO] Usando Playwright crawler")

        crawler = PlaywrightCrawler()
        pages = crawler.crawl(SEED_URL)

        if not pages:
            raise Exception("Playwright no devolvió páginas")

        print(f"[INFO] Playwright recuperó {len(pages)} páginas")

    except Exception as e:

        print(f"[WARN] Playwright falló: {e}")
        print("[INFO] Usando SiteCrawler fallback")

        crawler = SiteCrawler()
        pages = crawler.crawl([SEED_URL])

    total_pages = len(pages)

    print(f"\nTotal páginas recuperadas: {total_pages}\n")

    entity_index = {}

    total_entities = 0
    total_relations = 0

    for idx, page in enumerate(pages):

        url = page["url"]
        html = page["html"]

        print(f"\nProcesando página {idx+1}/{total_pages}: {url}")

        blocks = extractor.extract(html)

        page_entities = []
        page_text = ""

        for block in blocks:

            result = classifier.classify(block)

            if not result:
                continue

            entities = result["entities"]
            context = result["description"]
            image = result.get("image")

            page_text += " " + context

            for entity_text in entities:

                # limpieza semántica
                entity_text = cleaner.clean(entity_text)

                if not entity_text:
                    continue

                if len(entity_text.split()) > 8:
                    continue

                ontology_class = entity_resolver.resolve(
                    entity_text,
                    context,
                    image
                )

                if not ontology_class:
                    continue

                key = canonicalizer.canonical_key(entity_text)

                if key in entity_index:

                    entity_uri = entity_index[key]

                else:

                    entity_uri = rdf_builder.add_instance(
                        entity_name=entity_text,
                        ont_class=ontology_class,
                        label=entity_text
                    )

                    rdf_builder.add_provenance(
                        entity_uri,
                        url,
                        0.85,
                        "hybrid_extractor"
                    )

                    # Wikidata linking
                    wd_uri = wikidata_linker.search(entity_text)

                    if wd_uri:
                        rdf_builder.add_same_as(entity_uri, wd_uri)

                    entity_index[key] = entity_uri

                    total_entities += 1

                page_entities.append(entity_text)

        # extracción de relaciones
        relations = relation_extractor.extract(page_entities, page_text)

        for s, p, o in relations:

            s_uri = entity_index.get(canonicalizer.canonical_key(s))
            o_uri = entity_index.get(canonicalizer.canonical_key(o))

            if not s_uri or not o_uri:
                continue

            rdf_builder.add_object_property(s_uri, p, o_uri)

            total_relations += 1

    print("\n=== RESULTADOS ===\n")

    print(f"Entidades extraídas: {total_entities}")
    print(f"Relaciones detectadas: {total_relations}")

    rdf_builder.save("knowledge_graph.ttl")

    print("\nKnowledge Graph guardado en knowledge_graph.ttl")

    end_time = time.time()

    print(f"\nTiempo total: {round(end_time-start_time,2)}s")


if __name__ == "__main__":
    main()