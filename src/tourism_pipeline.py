from src.html_block_extractor import HTMLBlockExtractor
from src.tourism_entity_extractor import TourismEntityExtractor

from src.entity_cleaner import EntityCleaner
from src.entities.entity_deduplicator import EntityDeduplicator
from src.entities.entity_normalizer import EntityNormalizer
from src.entity_expander import EntityExpander
from src.entities.entity_splitter import EntitySplitter

from src.ontology_index import OntologyIndex

from src.poi.poi_discovery import POIDiscovery
from src.events.event_detector import EventDetector

from src.semantic.semantic_type_guesser import SemanticTypeGuesser
from src.semantic.semantic_similarity_matcher import SemanticSimilarityMatcher

from src.semantic.relation_extractor import RelationExtractor

from src.property_enricher import PropertyEnricher
from src.linking.wikidata_linker import WikidataLinker
from src.description_extractor import DescriptionExtractor
from src.image_enricher import ImageEnricher

from src.llm.llm_supervisor import LLMSupervisor
from src.entities.entity_ranker import EntityRanker
from src.entities.entity_clusterer import EntityClusterer

from src.entities.entity_scorer import EntityScorer
from src.entities.global_entity_memory import GlobalEntityMemory
from src.entities.entity_graph_builder import EntityGraphBuilder

import re
import hashlib
from difflib import SequenceMatcher


def normalize_text(text):
    text = text.lower()
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def text_hash(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def is_similar(a, b, threshold=0.90):
    return SequenceMatcher(None, a, b).ratio() > threshold



# ==================================================
# FIX ENCODING 🔥
# ==================================================
def fix_encoding(text):
    try:
        return text.encode("latin1").decode("utf-8")
    except:
        return text


# ==================================================
# TRIM
# ==================================================
def smart_trim(entity):
    words = entity.split()
    if len(words) <= 4:
        return entity
    if "de" in words:
        return entity
    return " ".join(words[-4:])


class TourismPipeline:

    def __init__(self, ontology_path):

        self.block_extractor = HTMLBlockExtractor()
        self.entity_extractor = TourismEntityExtractor()

        self.cleaner = EntityCleaner()
        self.deduplicator = EntityDeduplicator()
        self.normalizer = EntityNormalizer()
        self.expander = EntityExpander()
        self.splitter = EntitySplitter()

        self.ontology_index = OntologyIndex(ontology_path)

        self.poi_discovery = POIDiscovery()
        self.event_detector = EventDetector()

        self.type_guesser = SemanticTypeGuesser()
        self.semantic_matcher = SemanticSimilarityMatcher(self.ontology_index)

        self.relation_extractor = RelationExtractor()

        self.property_enricher = PropertyEnricher(self.ontology_index)
        self.wikidata_linker = WikidataLinker()
        self.description_extractor = DescriptionExtractor()
        self.image_enricher = ImageEnricher()

        self.llm_supervisor = LLMSupervisor(self.ontology_index)
        self.ranker = EntityRanker()
        self.clusterer = EntityClusterer()

        self.global_memory = GlobalEntityMemory()
        self.entity_scorer = EntityScorer()
        self.graph_builder = EntityGraphBuilder()

    # ==================================================
    # FILTRO ENTIDAD
    # ==================================================
    def is_valid_entity(self, entity):

        if not entity:
            return False

        e = entity.lower()
        words = entity.split()

        if len(entity) < 4:
            return False

        if len(words) > 6:
            return False

        # 🔥 basura típica
        if any(x in e for x in [
            "agenda",
            "eventos",
            "disfruta",
            "descubre",
            "todo lo que necesitas"
        ]):
            return False

        # 🔥 basura encoding
        if "Ã" in entity:
            return False

        return True

    # ==================================================
    # FILTRO BLOQUES
    # ==================================================
    def is_valid_block(self, text):

        if not text:
            return False

        t = text.lower()

        if any(x in t for x in [
            "phone number",
            "id card",
            "correo",
            "social media",
            "password",
            "login",
            "register"
        ]):
            return False

        if len(text) < 40:
            return False

        return True

    # ==================================================
    # PIPELINE
    # ==================================================
    def run(self, html):

        blocks = self.block_extractor.extract(html)
        results = []
        
        seen_texts = []

        for block in blocks:

            text = block.get("text", "") if isinstance(block, dict) else block

            # 🔥 normalizar texto
            normalized = normalize_text(text)

            # 🔥 evitar duplicados similares
            skip = False
            for seen in seen_texts:
                if is_similar(normalized, seen):
                    skip = True
                    break

            if skip:
                continue

            seen_texts.append(normalized)


            # 🔥 FIX encoding
            text = fix_encoding(text)

            
            if not self.is_valid_block(text):
                continue

            print("\n--- TEXTO BLOQUE ---")
            print(text[:120])

            # =========================================
            # 1️⃣ EXTRACCIÓN HÍBRIDA
            # =========================================

            entities = self.entity_extractor.extract(text)

            # LLM extracción
            try:
                llm_entities = self.llm_supervisor.extract_entities(text)
                entities.extend(llm_entities)
            except:
                pass

            entities.extend(self.event_detector.detect(text))
            entities.extend(self.poi_discovery.discover(text))

            # =========================================
            # 2️⃣ LIMPIEZA
            # =========================================

            entities = self.cleaner.clean(entities)
            entities = [e for e in entities if self.is_valid_entity(e)]
            entities = self.deduplicator.deduplicate(entities)
            entities = self.normalizer.normalize(entities)

            # split controlado
            split_entities = []
            for e in entities:
                parts = self.splitter.split(e)
                split_entities.extend(parts if parts else [e])

            entities = split_entities

            # trim
            entities = [smart_trim(e) for e in entities]

            # deduplicación final 🔥
            entities = list(set(entities))

            print("ENTIDADES FINAL:", entities)

            if not entities:
                continue

            # =========================================
            # 3️⃣ LLM SUPERVISOR
            # =========================================

            classified_entities = []

            try:
                llm_entities = self.llm_supervisor.analyze_entities(entities, text)
            except:
                llm_entities = []

            # 🔥 fallback si LLM falla
            if not llm_entities:
                for entity in entities:
                    classified_entities.append({
                        "entity": entity,
                        "class": "Place",
                        "score": 0.5,
                        "properties": {},
                        "short_description": "",
                        "long_description": ""
                    })
            else:
                for e in llm_entities:

                    entity = e.get("entity")
                    label = e.get("class", "Place")
                    score = e.get("score", 0.8)

                    props = self.property_enricher.enrich(entity, label, text)

                    # imagen
                    props.update(self.image_enricher.enrich(entity, text))

                    # wikidata
                    link = self.wikidata_linker.link(entity)
                    if link:
                        wikidata_props = self.wikidata_linker.get_entity_data(link["id"])
                        props.update(wikidata_props)

                        if "image" in wikidata_props:
                            props["image"] = wikidata_props["image"]

                    classified_entities.append({
                        "entity": entity,
                        "class": label,
                        "score": score,
                        "properties": props,
                        "short_description": e.get("short_description", ""),
                        "long_description": e.get("long_description", "")
                    })
            classified_entities = self.ranker.rank(classified_entities, text)
            classified_entities = self.clusterer.merge_clusters(classified_entities)


            # actualizar memoria global
            self.global_memory.update(classified_entities)

            global_counts = self.global_memory.get_counts()

            # recalcular score PRO
            for e in classified_entities:
                e["score"] = self.entity_scorer.compute_importance(e, text, global_counts)

            # ordenar final
            classified_entities = sorted(
                classified_entities,
                key=lambda x: x["score"],
                reverse=True
            )


            # 🔥 EXTRAER RELACIONES
            relations = self.relation_extractor.extract(text)

            # 🔥 AÑADIR AL GRAFO (nivel DIOS)
            self.graph_builder.add_relations(relations)

            # 🔥 GUARDAR RESULTADO
            results.append({
                "text": text,
                "entities": classified_entities,
                "relations": relations
            })
            
            print("Relaciones:", relations)

        return results
