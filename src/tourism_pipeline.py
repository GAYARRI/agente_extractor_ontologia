from src.html_block_extractor import HTMLBlockExtractor
from src.tourism_entity_extractor import TourismEntityExtractor

from src.entity_cleaner import EntityCleaner
from src.entities.entity_deduplicator import EntityDeduplicator
from src.entities.entity_normalizer import EntityNormalizer
from src.entity_expander import EntityExpander
from src.entities.entity_splitter import EntitySplitter

from src.ontology_index import OntologyIndex
from src.ontology_matcher import OntologyMatcher

from src.poi.poi_discovery import POIDiscovery
from src.events.event_detector import EventDetector

from src.semantic.semantic_type_guesser import SemanticTypeGuesser
from src.semantic.semantic_similarity_matcher import SemanticSimilarityMatcher
from src.semantic.relation_extractor import RelationExtractor

from src.ontology.ontology_auto_expander import TourismOntologyAutoExpander

from src.property_enricher import PropertyEnricher
from src.linking.wikidata_linker import WikidataLinker
from src.description_extractor import DescriptionExtractor
from src.image_enricher import ImageEnricher
from src.llm.llm_supervisor import LLMSupervisor



# ==================================================
# HEURÍSTICA SIMPLE
# ==================================================

def heuristic_class(entity):

    e = entity.lower()

    if "carnaval" in e:
        return "Festival"
    if "valle" in e:
        return "Valley"
    if "montaña" in e:
        return "NaturalArea"
    if "playa" in e:
        return "Beach"
    if "puerto" in e or "marina" in e:
        return "Marina"
    if "san bartolomé" in e:
        return "Municipality"
    if "atlántico" in e:
        return "Ocean"

    return None


# ==================================================
# NORMALIZACIÓN EVENTOS
# ==================================================

def normalize_event(entity):

    e = entity.lower()

    if "romería" in e:
        return "Romería de Piedraescrita"

    if "chanfaina" in e:
        return "Fiesta de la Chanfaina"

    if "semana santa" in e:
        return "Semana Santa"

    return entity


# ==================================================
# TRIM INTELIGENTE
# ==================================================

def smart_trim(entity):

    words = entity.split()

    if len(words) <= 4:
        return entity

    if "de" in words:
        return entity

    return " ".join(words[-4:])


# ==================================================
# PIPELINE
# ==================================================

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
        self.matcher = OntologyMatcher(self.ontology_index)

        self.poi_discovery = POIDiscovery()
        self.event_detector = EventDetector()
        self.type_guesser = SemanticTypeGuesser()

        self.semantic_matcher = SemanticSimilarityMatcher(self.ontology_index)

        self.relation_extractor = RelationExtractor()
        self.ontology_expander = TourismOntologyAutoExpander()

        self.property_enricher = PropertyEnricher(self.ontology_index)
        self.wikidata_linker = WikidataLinker()
        self.description_extractor = DescriptionExtractor()
        self.image_enricher = ImageEnricher()
        
        self.llm_supervisor = LLMSupervisor()

    # ==================================================
    # FILTRO DE ENTIDADES
    # ==================================================

    def is_valid_entity(self, entity):

        if not entity:
            return False

        e = entity.lower()
        words = entity.split()

        if len(words) > 6:
            return False

        if len(entity) < 4:
            return False

        # 🔥 eliminar basura real
        if any(x in e for x in [
            "agenda y eventos",
            "piedraescrita semana",
            "piedraescrita fiesta"
        ]):
            return False

        # 🔥 evitar genéricos inútiles
        if e in ["montaña", "playa", "mar"]:
            return False

        return True

    # ==================================================
    # PIPELINE PRINCIPAL
    # ==================================================

    def run(self, html):

        blocks = self.block_extractor.extract(html)
        results = []

        for block in blocks:

            text = block.get("text", "") if isinstance(block, dict) else block

            if not text or len(text) < 40:
                continue

            print("\n--- TEXTO BLOQUE ---")
            print(text[:120])

            # 1️⃣ extracción
            entities = self.entity_extractor.extract(text)

            # eventos
            for e in self.event_detector.detect(text):
                if e not in entities:
                    entities.append(e)

            # POIs
            for p in self.poi_discovery.discover(text):
                if p not in entities:
                    entities.append(p)

            # 2️⃣ limpieza
            entities = self.cleaner.clean(entities)

            # 3️⃣ filtro
            entities = [e for e in entities if self.is_valid_entity(e)]

            # 4️⃣ deduplicación
            entities = self.deduplicator.deduplicate(entities)

            # 5️⃣ normalización
            entities = self.normalizer.normalize(entities)

            # 6️⃣ normalizar eventos
            entities = [normalize_event(e) for e in entities]

            # 7️⃣ expansión CONTROLADA
            expanded = []
            for e in entities:

                # 🔥 NO expandir eventos
                if any(x in e.lower() for x in ["fiesta", "romería", "semana santa"]):
                    expanded.append(e)
                    continue

                try:
                    exp = self.expander.expand(e, text)

                    if exp and len(exp.split()) <= 6:
                        expanded.append(exp)
                    else:
                        expanded.append(e)

                except:
                    expanded.append(e)

            entities = expanded

            # 8️⃣ split
            split_entities = []

            for e in entities:
                try:
                    parts = self.splitter.split(e)

                    if parts:
                        split_entities.extend(parts)
                    else:
                        split_entities.append(e)

                except:
                    split_entities.append(e)

            entities = split_entities

            # 9️⃣ trim
            entities = [smart_trim(e) for e in entities]

            print("ENTIDADES POST-PROCESO:", entities)

            if not entities:
                continue

            # 🔥 LLM SUPERVISIÓN
            llm_entities = self.llm_supervisor.analyze_entities(entities, text)

            classified_entities = []

            for e in llm_entities:

                entity = e.get("entity")
                label = e.get("class", "Place")
                score = e.get("score", 0.8)

                # propiedades clásicas
                props = self.property_enricher.enrich(entity, label, text)

                # imagen
                image_props = self.image_enricher.enrich(entity, text)
                props.update(image_props)

                # fallback imagen
                if "image" not in props:
                    props["image"] = ""

                classified_entities.append({
                    "entity": entity,
                    "class": label,
                    "score": score,
                    "properties": props,
                    "short_description": e.get("short_description", ""),
                    "long_description": e.get("long_description", "")
                })



            # 🔟 clasificación + enriquecimiento
            for entity in entities:

                context = f"{entity} {text[:120]}"

                guessed = heuristic_class(entity) or self.type_guesser.guess(entity)

                if guessed:
                    label = guessed
                    score = 0.90
                else:
                    match = self.semantic_matcher.match(context)

                    if match:
                        label = match.get("label", "Place")
                        score = match.get("score", 0.5)
                    else:
                        label = "Place"
                        score = 0.3

                # propiedades
                props = self.property_enricher.enrich(entity, label, text)

                # 🔥 imágenes
                image_props = self.image_enricher.enrich(entity, text)
                props.update(image_props)

                # 🔥 fallback imagen
                if "image" not in props:
                    props["image"] = ""

                # descripciones
                descriptions = self.description_extractor.extract(entity, text)

                # wikidata
                link = self.wikidata_linker.link(entity)
                if link:
                    props["wikidata"] = link["id"]

                print("DEBUG ENTITY:", entity)
                print("DEBUG CLASS:", label)
                print("DEBUG PROPS:", props)

                classified_entities.append({
                    "entity": entity,
                    "class": label,
                    "score": score,
                    "properties": props,
                    "short_description": descriptions["short_description"],
                    "long_description": descriptions["long_description"]
                })

            # deduplicación final
            unique = {}
            for e in classified_entities:
                key = e["entity"].lower()
                if key not in unique or e["score"] > unique[key]["score"]:
                    unique[key] = e

            classified_entities = list(unique.values())

            relations = self.relation_extractor.extract(text)

            results.append({
                "text": text,
                "entities": classified_entities,
                "relations": relations
            })

        return results