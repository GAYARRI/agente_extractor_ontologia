import time
from dotenv import load_dotenv

from src.firecrawl_client import FirecrawlClient
from src.ner_extractor import NERExtractor
from src.ontology_loader import OntologyLoader
from src.entity_type_resolver import EntityTypeResolver
from src.relation_extractor import RelationExtractor
from src.tourism_property_extractor import TourismPropertyExtractor
from src.rdf_builder import RDFBuilder
from src.html_block_extractor import HTMLBlockExtractor
from src.block_classifier import BlockClassifier


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
}

RELATION_MAP = {
    "locatedIn": "hasLocation",
    "partOf": "relatedTo",
    "hasEvent": "relatedEvent",
    "near": "relatedTo",
    "offers": "offers",
}


def normalize_entity_key(text: str) -> str:
    return " ".join(text.strip().lower().split())


def get_entity_text(entity):
    if hasattr(entity, "normalized_text") and entity.normalized_text:
        return entity.normalized_text
    if hasattr(entity, "text"):
        return entity.text
    if isinstance(entity, dict):
        return entity.get("normalized_text") or entity.get("text")
    return None


def progress_bar(current, total, width=30):
    if total == 0:
        return "[Sin datos]"
    ratio = current / total
    filled = int(ratio * width)
    bar = "█" * filled + "-" * (width - filled)
    return f"[{bar}] {current}/{total} ({ratio:.1%})"


def is_valid_entity_candidate(text: str) -> bool:
    if not text:
        return False

    clean = normalize_entity_key(text)

    if len(clean) < 3:
        return False

    if clean in STOP_ENTITIES:
        return False

    banned_fragments = [
        "copy link",
        "watch later",
        "tap to unmute",
        "youtube",
        "please try again later",
        "photo image",
    ]

    if any(b in clean for b in banned_fragments):
        return False

    return True


def main():
    load_dotenv()
    global_start = time.time()

    seed_url = "https://turismo.maspalomas.com/"

    print("\n=== INICIALIZANDO COMPONENTES ===")
    fc = FirecrawlClient()
    ner_extractor = NERExtractor()
    relation_extractor = RelationExtractor()
    rdf_builder = RDFBuilder()
    block_extractor = HTMLBlockExtractor()
    block_classifier = BlockClassifier()

    print("\n=== CARGANDO ONTOLOGÍA ===")
    ontology_loader = OntologyLoader("ontology/core.ttl")
    ontology_data = ontology_loader.load()

    entity_resolver = EntityTypeResolver(ontology_data["classes"])
    property_extractor = TourismPropertyExtractor()

    print("\n=== CRAWLING CON FIRECRAWL ===")
    crawl_result = fc.crawl_site(seed_url, limit=50)

    pages = []

    for item in crawl_result.data:
        # Firecrawl puede devolver objetos Pydantic Document;
        # el fallback devuelve dicts normales.
        if hasattr(item, "model_dump"):
            item_dict = item.model_dump()
        else:
            item_dict = item

        metadata = item_dict.get("metadata", {}) or {}

        pages.append(
            {
                "url": metadata.get("sourceURL", "") or "",
                "html": item_dict.get("html", "") or "",
                "text": item_dict.get("markdown", "") or item_dict.get("html", "") or "",
            }
        )

    total_pages = len(pages)
    print(f"\nTotal de páginas recuperadas: {total_pages}")

    if total_pages == 0:
        print("No se recuperaron páginas.")
        return

    entity_index = {}

    total_detected_entities = 0
    total_linked_entities = 0
    total_relations = 0

    print("\n=== INICIANDO EXTRACCIÓN POR BLOQUES ===")

    for idx, page in enumerate(pages, start=1):
        page_start = time.time()

        url = page.get("url") or ""
        html = page.get("html") or ""
        text = page.get("text") or ""

        print("\n" + "=" * 80)
        print(f"PROGRESO {progress_bar(idx, total_pages)}")
        print(f"Procesando: {url}")
        print(f"Longitud html: {len(html)}")
        print(f"Longitud text: {len(text)}")
        print(f"Preview text: {text[:300]!r}")

        if not html and not text:
            print("HTML y texto vacíos")
            continue

        blocks = block_extractor.extract_blocks(html, page_url=url)
        print(f"Bloques detectados: {len(blocks)}")

        if not blocks and text:
            print("No se detectaron bloques HTML; usando bloque fallback desde text")
            blocks = [
                {
                    "block_id": "fallback_block",
                    "heading": "",
                    "text": text,
                    "image": None,
                    "links": [],
                    "page_url": url,
                }
            ]

        if not blocks:
            continue

        page_entities = []
        page_relation_count = 0

        for block_idx, block in enumerate(blocks, start=1):
            block_text = block.get("text", "") or ""
            block_heading = block.get("heading", "") or ""

            block_info = block_classifier.classify_block(block)
            block_is_collective = block_info["is_collective"]

            print(f"  [BLOQUE {block_idx}] heading='{block_heading[:80]}'")
            print(
                f"    colectivo={block_is_collective} "
                f"score={block_info['score']:.2f} "
                f"reasons={block_info['reasons']}"
            )
            print(f"    Texto bloque (primeros 200 chars): {block_text[:200]!r}")

            if not block_text or len(block_text.strip()) < 40:
                continue

            try:
                block_entities = ner_extractor.extract_from_block(block)
            except Exception as e:
                print(f"    Error NER bloque: {e}")
                block_entities = []

            detected_in_block = len(block_entities)
            total_detected_entities += detected_in_block

            print(f"    Entidades detectadas: {detected_in_block}")
            if block_entities:
                print(f"    Muestra entidades: {block_entities[:5]}")

            block_page_entities = []

            for entity in block_entities:
                entity_text = get_entity_text(entity)

                if not entity_text:
                    continue

                entity_text = entity_text.strip()

                if not is_valid_entity_candidate(entity_text):
                    continue

                entity_key = normalize_entity_key(entity_text)

                try:
                    block_properties = property_extractor.extract_from_block(
                        block,
                        entity_text,
                        block_is_collective=block_is_collective,
                    )
                except Exception as e:
                    print(f"    Error propiedades bloque: {e}")
                    block_properties = {}

                result = entity_resolver.resolve(
                    mention=entity_text,
                    context=block_text[:800],
                    description=block_properties.get("description", ""),
                    url=url,
                    properties=block_properties,
                    top_k=5,
                )

                ontology_class = result["class"]
                confidence = result["confidence"]

                print(f"    [ENTITY] {entity_text} -> {ontology_class} ({confidence:.3f})")
                print(f"            top={result['top_candidates'][:3]}")

                total_linked_entities += 1

                if entity_key not in entity_index:
                    entity_uri = rdf_builder.add_instance(
                        entity_name=entity_text,
                        ont_class=ontology_class,
                        label=entity_text,
                    )

                    rdf_builder.add_provenance(
                        entity_uri,
                        source_url=url,
                        confidence=confidence,
                        extractor="entity_type_resolver_block",
                    )

                    entity_index[entity_key] = {
                        "text": entity_text,
                        "uri": entity_uri,
                        "class": ontology_class,
                        "confidence": confidence,
                    }
                else:
                    entity_uri = entity_index[entity_key]["uri"]

                entity_record = {
                    "text": entity_text,
                    "key": entity_key,
                    "uri": entity_uri,
                    "class": ontology_class,
                    "confidence": confidence,
                    "block_id": block.get("block_id"),
                }

                page_entities.append(entity_record)
                block_page_entities.append(entity_record)

                if isinstance(block_properties, dict):
                    for prop_name, prop_value in block_properties.items():
                        if not prop_value:
                            continue

                        rdf_builder.add_data_property(
                            subject=entity_uri,
                            prop_name=prop_name,
                            value=prop_value,
                        )

            try:
                block_relations = relation_extractor.extract(block_page_entities, block_text)
            except Exception as e:
                print(f"    Error relaciones bloque: {e}")
                block_relations = []

                for rel in block_relations:
                    subject_text = rel.get("subject")
                    raw_predicate = rel.get("predicate")
                    object_text = rel.get("object")
                    rel_confidence = rel.get("confidence", 0.0)

                    if not subject_text or not raw_predicate or not object_text:
                        continue

                    predicate = RELATION_MAP.get(raw_predicate, raw_predicate)

                    subject_key = normalize_entity_key(subject_text)
                    object_key = normalize_entity_key(object_text)

                    if subject_key not in entity_index or object_key not in entity_index:
                        continue

                subject_uri = entity_index[subject_key]["uri"]
                object_uri = entity_index[object_key]["uri"]

                rdf_builder.add_object_property(
                    subject=subject_uri,
                    prop_name=predicate,
                    obj=object_uri,
                )

                rdf_builder.add_provenance(
                    subject_uri,
                    source_url=url,
                    confidence=rel_confidence,
                    extractor="relation_extractor_block",
                )

                page_relation_count += 1
                total_relations += 1

        print(f"Entidades aceptadas en página: {len(page_entities)}")
        print(f"Relaciones extraídas: {page_relation_count}")
        print(f"Triples acumulados: {rdf_builder.size()}")
        print(f"Tiempo página: {time.time() - page_start:.2f}s")

    print("\n=== GUARDANDO KG ===")
    output_path = "knowledge_graph.ttl"
    rdf_builder.save(output_path)

    total_time = time.time() - global_start

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