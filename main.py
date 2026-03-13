import time
from dotenv import load_dotenv
import os

from src import site_crawler
from src import playwright_crawler
from src.firecrawl_client import FirecrawlClient
from src.site_crawler import SiteCrawler
from firecrawl import FirecrawlApp





from src.html_block_extractor import HTMLBlockExtractor
from src.block_classifier import BlockClassifier

from src.ner_extractor import NERExtractor
from src.relation_extractor import RelationExtractor
from src.tourism_property_extractor import TourismPropertyExtractor
from src.rdf_builder import RDFBuilder
from src.ontology_loader import OntologyLoader
from src.playwright_crawler import PlaywrightCrawler
from src.entity_type_resolver import EntityTypeResolver


# --------------------------------------------------
# ENTIDADES BASURA
# --------------------------------------------------

STOP_ENTITIES = {
    "cookies",
    "search",
    "share",
    "copy link",
    "watch later",
    "tap to unmute",
    "youtube",
}


# --------------------------------------------------
# NORMALIZAR ENTIDAD
# --------------------------------------------------

def normalize_entity_key(text: str) -> str:
    return " ".join(text.strip().lower().split())


# --------------------------------------------------
# VALIDAR ENTIDAD
# --------------------------------------------------

def is_valid_entity_candidate(text: str) -> bool:

    if not text:
        return False

    clean = normalize_entity_key(text)

    if len(clean) < 3:
        return False

    if clean in STOP_ENTITIES:
        return False

    return True


# --------------------------------------------------
# PROGRESS BAR
# --------------------------------------------------

def progress_bar(current, total, width=30):

    if total == 0:
        return "[Sin datos]"

    ratio = current / total
    filled = int(ratio * width)

    bar = "█" * filled + "-" * (width - filled)

    return f"[{bar}] {current}/{total} ({ratio:.1%})"


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    load_dotenv()

    start_time = time.time()

    seed_url = "https://turismoapps.dip-badajoz.es/"

    print("\n=== INICIALIZANDO COMPONENTES ===")

    fc = FirecrawlClient()

    crawler = SiteCrawler(max_pages=50)

    playwright_crawler = PlaywrightCrawler(max_pages=1000)

    block_extractor = HTMLBlockExtractor()

    block_classifier = BlockClassifier()

    ner_extractor = NERExtractor()

    relation_extractor = RelationExtractor()

    property_extractor = TourismPropertyExtractor()

    rdf_builder = RDFBuilder()

    print("\n=== CARGANDO ONTOLOGÍA ===")

    ontology_loader = OntologyLoader("ontology/core.ttl")

    ontology_data = ontology_loader.load()

    entity_resolver = EntityTypeResolver()

    # --------------------------------------------------
    # CRAWL
    # --------------------------------------------------

    print("\n=== CRAWLING ===")

    pages = None

    # --------------------------------------------------
    # 1️⃣ FIRECRAWL
    # --------------------------------------------------

    try:

        crawl_result = fc.crawl_site(seed_url, limit=1000)

        pages = []

        FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

        fc = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

        if crawl_result and hasattr(crawl_result, "__iter__"):

            for item in crawl_result:

                html = getattr(item, "content", None)

                if not html:
                    continue

                pages.append({
                    "url": item.metadata.get("sourceURL", ""),
                    "html": html,
                    "text": html
                })

        if not pages:
            
            raise Exception("Firecrawl no devolvió páginas")

        print(f"[INFO] Firecrawl recuperó {len(pages)} páginas")

    except Exception as e:

        print("[WARN] Firecrawl falló:", e)

        # --------------------------------------------------
        # 2️⃣ PLAYWRIGHT
        # --------------------------------------------------

        try:

            print("[INFO] Activando Playwright crawler...")

            pages = playwright_crawler.crawl(seed_url)
            

            if not pages:
                raise Exception("Playwright no devolvió páginas")
            total_pages = len(pages)

            print(f"[INFO] Playwright recuperó {len(pages)} páginas")

        except Exception as e:

            print("[WARN] Playwright falló:", e)

            # --------------------------------------------------
            # 3️⃣ SITECRAWLER
            # --------------------------------------------------

            print("[INFO] Activando fallback con SiteCrawler...")

            pages = site_crawler.crawl_site(seed_url)

            print(f"[INFO] SiteCrawler recuperó {len(pages)} páginas")

    # --------------------------------------------------
    # INDICE DE ENTIDADES
    # --------------------------------------------------

    entity_index = {}

    total_detected_entities = 0
    total_linked_entities = 0
    total_relations = 0

    # --------------------------------------------------
    # PROCESAR PAGINAS
    # --------------------------------------------------

    for idx, page in enumerate(pages, start=1):

        page_entities=[]

        url = page.get("url")

        html = page.get("html")

        if not html:
            continue

        print("\n" + "=" * 80)
        print(f"PROGRESO {progress_bar(idx, total_pages)}")
        print(f"Procesando: {url}")

        blocks = block_extractor.extract_blocks(html)

        for block in blocks:

            block_html = block.get("html")

            entities = []

            # --------------------------------------------------
            # 1. CLASIFICADOR
            # --------------------------------------------------

            result = block_classifier.classify_block(block_html)

            if result:

                entity_text = result["entity_candidate"]

                if is_valid_entity_candidate(entity_text):
                    entities.append(entity_text)

            # --------------------------------------------------
            # 2. FALLBACK NER
            # --------------------------------------------------

            if not entities:

                ner_entities = ner_extractor.extract(block.get("text", ""))

                for ent in ner_entities:

                    entity_text = ent["text"]

                    if is_valid_entity_candidate(entity_text):
                        entities.append(entity_text)

            if not entities:
                continue

            # --------------------------------------------------
            # PROCESAR ENTIDADES
            # --------------------------------------------------

            for entity_text in entities:

                total_detected_entities += 1

                properties = property_extractor.extract_from_block(
                    block,
                    entity_text
                )

                context = block.get("text", "")

                resolution = entity_resolver.resolve(
                    mention=entity_text,
                    context=url,
                    block_text=context
                    
                )
                 
                ontology_class = resolution["class"].lower()
                confidence = resolution["confidence"]

                # filtrar entidades con poca confianza
                if confidence < 0.4:
                    continue

                entity_key = normalize_entity_key(entity_text)

                if len(entity_key) < 3:
                    continue

                print(f"[ENTITY] {entity_text} -> {ontology_class} ({confidence:.3f})")

                total_linked_entities += 1

                if entity_key not in entity_index:

                    entity_uri = rdf_builder.add_instance(
                        entity_name=entity_text,
                        ont_class=ontology_class,
                        label=entity_text
                    )

                    page_entities.append({
                        "text": entity_text,
                        "uri": entity_uri
                    })                      


                    rdf_builder.add_provenance(
                        entity_uri,
                        source_url=url,
                        confidence=confidence,
                        extractor="hybrid_extractor"
                    )

                    entity_index[entity_key] = {
                        "uri": entity_uri,
                        "class": ontology_class,
                        "confidence": confidence
                    } 
                

                else:

                    entity_uri = entity_index[entity_key]["uri"]

                # propiedades RDF

                for prop_name, prop_value in properties.items():

                    if not prop_value:
                        continue

                    rdf_builder.add_data_property(
                        subject=entity_uri,
                        prop_name=prop_name,
                        value=prop_value
                    )

        # --------------------------------------------------
        # RELACIONES
        # --------------------------------------------------

        relations = relation_extractor.extract(page_entities, html)

        for rel in relations:

            subject = rel.get("subject")
            predicate = rel.get("predicate")
            obj = rel.get("object")

            if not subject or not obj:
                continue

            subject_key = normalize_entity_key(subject)
            object_key = normalize_entity_key(obj)

            if subject_key not in entity_index:
                continue

            if object_key not in entity_index:
                continue

            subject_uri = entity_index[subject_key]["uri"]
            object_uri = entity_index[object_key]["uri"]

            rdf_builder.add_object_property(
                subject=subject_uri,
                prop_name=predicate,
                obj=object_uri
            )

            total_relations += 1

    # --------------------------------------------------
    # GUARDAR KG
    # --------------------------------------------------

    print("\n=== GUARDANDO KG ===")

    output_path = "knowledge_graph.ttl"

    rdf_builder.save(output_path)

    total_time = time.time() - start_time

    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)

    print(f"Páginas procesadas: {total_pages}")
    print(f"Entidades detectadas: {total_detected_entities}")
    print(f"Entidades vinculadas: {total_linked_entities}")
    print(f"Relaciones: {total_relations}")
    print(f"Triples totales: {rdf_builder.size()}")
    print(f"Tiempo total: {total_time:.2f}s")
    print(f"KG guardado en: {output_path}")


if __name__ == "__main__":
    main()