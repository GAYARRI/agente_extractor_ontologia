import os
from dotenv import load_dotenv

from src.site_crawler import SiteCrawler
from src.ner_extractor import NERExtractor
from src.ontology_loader import OntologyLoader
from src.ontology_entity_linker import OntologyEntityLinker
from src.relation_extractor import RelationExtractor
from src.tourism_property_extractor import TourismPropertyExtractor
from src.rdf_builder import RDFBuilder


def normalize_entity_key(text: str) -> str:
    return " ".join(text.strip().lower().split())


def get_entity_text(entity):
    if hasattr(entity, "text"):
        return entity.text
    if isinstance(entity, dict):
        return entity.get("text")
    return None


def main():
    load_dotenv()

    seed_urls = [
        "https://www.visitmadrid.es/donde-ir/area-metropolitana/rivas-vaciamadrid",
    ]

    crawler = SiteCrawler(max_pages=10)


    pages = crawler.crawl(seed_urls)
        
    print(f"Total de páginas recuperadas: {len(pages)}")

    ner_extractor = NERExtractor()
    relation_extractor = RelationExtractor()
    property_extractor = TourismPropertyExtractor()
    rdf_builder = RDFBuilder()

    ontology_loader = OntologyLoader("ontology/core.ttl")
    ontology_data = ontology_loader.load()

    entity_linker = OntologyEntityLinker(ontology_data["classes"])

    pages = crawler.crawl(seed_urls)
    print(f"Total de páginas recuperadas: {len(pages)}")

    # Índice global para no duplicar entidades en todo el KG
    entity_index = {}

    for page in pages:
        try:
            url = page.get("url")
            text = page.get("text", "")
            html = page.get("html", "")

            if not text or len(text.strip()) < 50:
                continue

            print(f"\nProcesando página: {url}")

            entities = ner_extractor.extract(text)
            print("Entidades detectadas:")
            print("Entidades detectadas:")
            for e in entities[:10]:
                print(e)

            page_entities = []

            for entity in entities:
                entity_text = get_entity_text(entity)

                if not entity_text:
                    continue

                entity_text = entity_text.strip()
                if not entity_text:
                    continue

                entity_key = normalize_entity_key(entity_text)

                # 1. Clasificación ontológica
                result = entity_linker.classify(entity_text)
                ontology_class = result["class"]
                confidence = result["confidence"]

                # filtro de confianza
                if confidence < 0.45:
                    continue

                # Guardar sobre el objeto si existe el atributo
                if hasattr(entity, "ontology_class"):
                    entity.ontology_class = ontology_class
                if hasattr(entity, "confidence"):
                    entity.confidence = confidence

                # 2. Crear instancia RDF una sola vez
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
                        extractor="ontology_entity_linker",
                    )

                    entity_index[entity_key] = {
                        "text": entity_text,
                        "uri": entity_uri,
                        "class": ontology_class,
                        "confidence": confidence,
                    }
                else:
                    entity_uri = entity_index[entity_key]["uri"]

                page_entities.append(
                    {
                        "text": entity_text,
                        "key": entity_key,
                        "uri": entity_uri,
                        "class": ontology_class,
                        "confidence": confidence,
                    }
                )

                # 3. Extraer propiedades
                
                try:
                    html = page.get("html", "")

                    extracted_properties = property_extractor.extract(
                        html=html,
                        text=text,
                        url=url,
                        entity=entity_text,
                    )

                    if isinstance(extracted_properties, dict):
                        for prop_name, prop_value in extracted_properties.items():
                            if prop_value is None or prop_value == "":
                                continue

                            rdf_builder.add_data_property(
                                subject=entity_uri,
                                prop_name=prop_name,
                                value=prop_value,
                            )

                except Exception as prop_error:
                    print(f"  [WARN] Error extrayendo propiedades para '{entity_text}': {prop_error}")    
                    

            # 4. Extraer relaciones entre entidades
            try:
                relations = relation_extractor.extract(page_entities, text)
            except Exception as rel_error:
                print(f"  [WARN] Error extrayendo relaciones en {url}: {rel_error}")
                relations = []

            for rel in relations:
                subject_text = rel.get("subject")
                predicate = rel.get("predicate")
                object_text = rel.get("object")
                rel_confidence = rel.get("confidence", 0.0)

                if not subject_text or not predicate or not object_text:
                    continue

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
                    extractor="relation_extractor",
                )

        except Exception as page_error:
            print(f"[ERROR] Fallo procesando página {page.get('url', 'unknown')}: {page_error}")
            continue

    output_path = "knowledge_graph.ttl"
    rdf_builder.save(output_path)

    print(f"\nKG generado correctamente en: {output_path}")
    print(f"Total de triples: {rdf_builder.size()}")


if __name__ == "__main__":
    main()