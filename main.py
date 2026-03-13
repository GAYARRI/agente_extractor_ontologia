import time
from dotenv import load_dotenv

from src.firecrawl_client import FirecrawlClient
from src.site_crawler import SiteCrawler

from src.html_block_extractor import HTMLBlockExtractor
from src.block_classifier import BlockClassifier

from src.ner_extractor import NERExtractor
from src.entity_type_resolver import EntityTypeResolver
from src.relation_extractor import RelationExtractor
from src.tourism_property_extractor import TourismPropertyExtractor
from src.rdf_builder import RDFBuilder
from src.ontology_loader import OntologyLoader


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
    "please try again later",
    "photo image of maspalomas",
    "wtm teaser not sub",
    "shopping",
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

    banned_fragments = [
        "watch later",
        "copy link",
        "tap to unmute",
        "youtube",
        "photo image",
        "please try again later",
        "teaser not sub",
    ]

    if any(b in clean for b in banned_fragments):
        return False

    return True


# --------------------------------------------------
# CLASE TURÍSTICA SEGURA
# --------------------------------------------------

def force_safe_tourism_class(entity_text: str, current_class: str, confidence: float) -> str:

    t = entity_text.lower()

    if "playa" in t:
        return "Cove"

    if "sendero" in t or "camino" in t or "ruta" in t:
        return "Trail"

    if "puerto" in t:
        return "YatchingPort"

    if "hotel" in t:
        return "Hotel"

    if "restaurante" in t:
        return "Restaurant"

    if "valle" in t:
        return "Valley"

    if "jardin" in t or "jardín" in t:
        return "Garden"

    if "carnaval" in t or "festival" in t:
        return "Event"

    if confidence < 0.32:
        return "Place"

    return current_class


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

    seed_url = "https://turismo.maspalomas.com/"

    print("\n=== INICIALIZANDO COMPONENTES ===")

    fc = FirecrawlClient()

    crawler = SiteCrawler(max_pages=50)

    block_extractor = HTMLBlockExtractor()

    block_classifier = BlockClassifier()

    ner_extractor = NERExtractor()

    relation_extractor = RelationExtractor()

    property_extractor = TourismPropertyExtractor()

    rdf_builder = RDFBuilder()

    print("\n=== CARGANDO ONTOLOGÍA ===")

    ontology_loader = OntologyLoader("ontology/core.ttl")

    ontology_data = ontology_loader.load()

    entity_resolver = EntityTypeResolver(ontology_data["classes"])

    # --------------------------------------------------
    # CRAWL
    # --------------------------------------------------

    print("\n=== CRAWLING CON FIRECRAWL ===")

    try:

        crawl_result = fc.crawl_site(seed_url, limit=1000)

        pages = []

        for item in crawl_result:

            html = getattr(item, "content", None)

            if not html:
                continue

            pages.append({
                "url": item.metadata.get("sourceURL", ""),
                "html": html,
                "text": html
            })

    except Exception as e:

        print("[WARN] Error SSL en Firecrawl:", e)
        print("[INFO] Activando fallback con SiteCrawler...")

        pages = crawler.crawl([seed_url])

    total_pages = len(pages)

    print(f"\nTotal de páginas recuperadas: {total_pages}")

    if total_pages == 0:
        return

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

        url = page.get("url")

        html = page.get("html")

        if not html:
            continue

        print("\n" + "=" * 80)
        print(f"PROGRESO {progress_bar(idx, total_pages)}")
        print(f"Procesando: {url}")

        blocks = block_extractor.extract_blocks(html)
        

        page_entities = []

        for block in blocks:

            block_html = block.get("html")

            # evitar bloques inválidos
            if not block_html or not isinstance(block_html, str):
                continue

            result = block_classifier.classify_block(block_html)            

            if not result:
                continue

            entity_text = result["entity_candidate"]

            if not is_valid_entity_candidate(entity_text):
                continue

            total_detected_entities += 1

            # ------------------------------------------
            # EXTRAER PROPIEDADES
            # ------------------------------------------

            properties = property_extractor.extract_from_block(
                html_block=block_html,
                url=url,
                entity_name=entity_text
            )

            context = result.get("text", "")

            description_hint = properties.get("description", "")

            # ------------------------------------------
            # RESOLVER TIPO
            # ------------------------------------------
            
            resolution = entity_resolver.resolve(
            mention=entity_text,
            context=context,
            description=description_hint,
            url=url,
            properties=properties,
            block_text=context
        )


            ontology_class = resolution["class"]

            confidence = resolution["confidence"]

            if confidence < 0.18:
                continue

            ontology_class = force_safe_tourism_class(
                entity_text,
                ontology_class,
                confidence
            )

            print(f"[ENTITY] {entity_text} -> {ontology_class} ({confidence:.3f})")

            total_linked_entities += 1

            entity_key = normalize_entity_key(entity_text)

            # ------------------------------------------
            # CREAR RDF
            # ------------------------------------------

            if entity_key not in entity_index:

                entity_uri = rdf_builder.add_instance(
                    entity_name=entity_text,
                    ont_class=ontology_class,
                    label=entity_text
                )

                rdf_builder.add_provenance(
                    entity_uri,
                    source_url=url,
                    confidence=confidence,
                    extractor="entity_type_resolver_block"
                )

                entity_index[entity_key] = {
                    "uri": entity_uri,
                    "class": ontology_class,
                    "confidence": confidence
                }

            else:

                entity_uri = entity_index[entity_key]["uri"]

            page_entities.append({
                "text": entity_text,
                "key": entity_key,
                "uri": entity_uri,
            })

            # ------------------------------------------
            # PROPIEDADES RDF
            # ------------------------------------------

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
