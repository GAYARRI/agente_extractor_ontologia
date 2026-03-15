from src.html_block_extractor import HTMLBlockExtractor
from src.ontology_index import OntologyIndex
from src.ontology_matcher import OntologyMatcher
from src.block_classifier import BlockClassifier

from src.entity_cleaner import EntityCleaner
from src.entities.entity_deduplicator import EntityDeduplicator


class TourismPipeline:

    def __init__(self, ontology_path):

        # extractor de bloques HTML
        self.block_extractor = HTMLBlockExtractor()

        # cargar ontología
        ontology_index = OntologyIndex(ontology_path)

        # matcher semántico
        matcher = OntologyMatcher(ontology_index)

        # clasificador de bloques
        self.classifier = BlockClassifier(matcher)

        # limpieza de entidades
        self.cleaner = EntityCleaner()

        # eliminación de duplicados
        self.deduplicator = EntityDeduplicator()


    def run(self, html):

        # 1️⃣ extraer bloques HTML
        blocks = self.block_extractor.extract(html)

        print("Bloques extraídos:", len(blocks))

        # debug: mostrar algunos bloques
        for b in blocks[:5]:
            print("Ejemplo bloque:", b["text"][:120])

        results = []

        # 2️⃣ procesar cada bloque
        for block in blocks:

            classified = self.classifier.classify(block)

            if not classified:
                continue

            if not isinstance(classified, dict):
                continue

            entities = classified.get("entities")

            if not entities:
                continue

            # 3️⃣ limpiar entidades
            entities = self.cleaner.clean(entities)

            if not entities:
                continue

            classified["entities"] = entities

            results.append(classified)

        # 4️⃣ eliminar duplicados globales
        results = self.deduplicator.deduplicate(results)

        print("Bloques con entidades:", len(results))

        return results