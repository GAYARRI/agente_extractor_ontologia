from src.html_block_extractor import HTMLBlockExtractor
from src.tourism_entity_extractor import TourismEntityExtractor
from src.entity_cleaner import EntityCleaner
from src.entities.entity_deduplicator import EntityDeduplicator

from src.ontology_index import OntologyIndex
from src.ontology_matcher import OntologyMatcher
from src.block_classifier import BlockClassifier

from src.poi.poi_discovery import POIDiscovery
from src.events.event_detector import EventDetector
from src.semantic.semantic_type_guesser import SemanticTypeGuesser

from src.entities.entity_normalizer import EntityNormalizer
from src.semantic.semantic_similarity_matcher import SemanticSimilarityMatcher
from src.semantic.relation_extractor import RelationExtractor
from src.ontology.ontology_auto_expander import TourismOntologyAutoExpander


class TourismPipeline:

    def __init__(self, ontology_path):

        # ------------------------------
        # BLOQUES HTML
        # ------------------------------

        self.block_extractor = HTMLBlockExtractor()

        # ------------------------------
        # EXTRACCIÓN DE ENTIDADES
        # ------------------------------

        self.entity_extractor = TourismEntityExtractor()

        # ------------------------------
        # LIMPIEZA
        # ------------------------------

        self.cleaner = EntityCleaner()
        self.deduplicator = EntityDeduplicator()
        self.normalizer = EntityNormalizer()

        # ------------------------------
        # ONTOLOGÍA
        # ------------------------------

        self.ontology_index = OntologyIndex(ontology_path)

        self.matcher = OntologyMatcher(self.ontology_index)

        self.classifier = BlockClassifier(
            self.ontology_index,
            self.matcher
        )

        # ------------------------------
        # DETECTORES SEMÁNTICOS
        # ------------------------------

        self.poi_discovery = POIDiscovery()
        self.event_detector = EventDetector()
        self.type_guesser = SemanticTypeGuesser()

        # ------------------------------
        # MATCHER SEMÁNTICO (EMBEDDINGS)
        # ------------------------------

        self.semantic_matcher = SemanticSimilarityMatcher(
            self.ontology_index
        )

        # ------------------------------
        # RELACIONES
        # ------------------------------

        self.relation_extractor = RelationExtractor()

        # ------------------------------
        # EXPANSIÓN DE ONTOLOGÍA
        # ------------------------------

        self.ontology_expander = TourismOntologyAutoExpander()

    # ==================================================
    # PIPELINE PRINCIPAL
    # ==================================================

    def run(self, html):

        blocks = self.block_extractor.extract(html)

        print("Bloques extraídos:", len(blocks))

        results = []

        for block in blocks:

            if isinstance(block, dict):
                text = block.get("text", "")
            else:
                text = block

            if not text or len(text) < 40:
                continue

            print("\n--- TEXTO BLOQUE ---")
            print(text[:120])

            # --------------------------------------------------
            # 1️⃣ ENTIDADES NLP
            # --------------------------------------------------

            entities = self.entity_extractor.extract(text)

            print("NLP entidades:", entities)

            # --------------------------------------------------
            # 2️⃣ EVENTOS
            # --------------------------------------------------

            events = self.event_detector.detect(text)

            print("Eventos detectados:", events)

            for e in events:
                if e not in entities:
                    entities.append(e)

            # --------------------------------------------------
            # 3️⃣ POIs
            # --------------------------------------------------

            pois = self.poi_discovery.discover(text)

            print("POIs detectados:", pois)

            for p in pois:
                if p not in entities:
                    entities.append(p)

            print("Entidades combinadas:", entities)

            # --------------------------------------------------
            # 4️⃣ LIMPIEZA
            # --------------------------------------------------

            entities = self.cleaner.clean(entities)

            print("Tras cleaner:", entities)

            # --------------------------------------------------
            # 5️⃣ DEDUPLICACIÓN
            # --------------------------------------------------

            entities = self.deduplicator.deduplicate(entities)

            print("Tras deduplicator:", entities)

            # --------------------------------------------------
            # 6️⃣ NORMALIZACIÓN SEMÁNTICA
            # --------------------------------------------------

            entities = self.normalizer.normalize(entities)

            print("Tras normalizer:", entities)

            if not entities:
                continue

            classified_entities = []

            # --------------------------------------------------
            # 7️⃣ CLASIFICACIÓN ONTOLÓGICA
            # --------------------------------------------------

            for entity in entities:

                context = f"{entity} {text[:120]}"

                # heurística rápida
                guessed = self.type_guesser.guess(entity)

                if guessed:

                    classified_entities.append({
                        "entity": entity,
                        "class": guessed,
                        "score": 0.90
                    })

                    continue

                # matcher semántico
                match = self.semantic_matcher.match(context)

                if not match:

                    classified_entities.append({
                        "entity": entity,
                        "class": "Unknown",
                        "score": 0.0
                    })

                    continue

                classified_entities.append({
                    "entity": entity,
                    "class": match.get("label", "Unknown"),
                    "score": match.get("score", 0.0)
                })

            # --------------------------------------------------
            # 8️⃣ RELACIONES
            # --------------------------------------------------

            relations = self.relation_extractor.extract(text)

            print("Relaciones detectadas:", relations)

            # --------------------------------------------------
            # 9️⃣ EXPANSIÓN DE ONTOLOGÍA
            # --------------------------------------------------

            suggested_classes = self.ontology_expander.discover_classes(text)

            print("Clases ontológicas sugeridas:", suggested_classes)

            # --------------------------------------------------
            # GUARDAR RESULTADOS
            # --------------------------------------------------

            results.append({

                "text": text,

                "entities": classified_entities,

                "relations": relations,

                "suggested_classes": suggested_classes

            })

        print("\nBloques con entidades:", len(results))

        return results