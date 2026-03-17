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

        self.property_enricher = PropertyEnricher()
        self.wikidata_linker = WikidataLinker()

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

        if len(words) == 1:
            if e in ["atlántico", "gran canaria"]:
                return True
            return True   # 🔥 permitir palabras simples (clave)

        # ruido web
        if any(x in e for x in [
            "indicadores",
            "calidad del aire",
            "flujos turísticos",
            "maps and brochures",
            "how to get"
        ]):
            return False

        # multilenguaje basura
        if any(x in e for x in [
            "wenn", "sie", "und", "der",
            "les", "des", "ne", "pas",
            "comment", "arriver",
            "aktivitäten", "umfragen"
        ]):
            return False

        # frases con verbos
        if any(v in e for v in [
            "vive", "explora", "descubre",
            "disfruta", "navega", "zarpa"
        ]):
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

            # 1️⃣ extracción base
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

            # 7️⃣ expansión
            expanded = []

            for e in entities:
                try:
                    exp = self.expander.expand(e, text)

                    # 🔥 solo aceptar si no se vuelve frase gigante
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


            # 9️⃣ trim final
            entities = [smart_trim(e) for e in entities]

            print("ENTIDADES POST-PROCESO:", entities)

            if not entities:
                continue

            classified_entities = []

            # 🔟 clasificación + enriquecimiento
            for entity in entities:

                context = f"{entity} {text[:120]}"

                guessed = heuristic_class(entity) or self.type_guesser.guess(entity)

                link = self.wikidata_linker.link(entity)
                wikidata_props = {}

                if link:
                    wikidata_props = self.wikidata_linker.get_entity_data(link["id"])





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

                # 🔥 PROPIEDADES SIEMPRE
                props = self.property_enricher.enrich(entity, label, text)

                # 🔥 añadir propiedades Wikidata
                if wikidata_props:
                    props.update(wikidata_props)

                def resolve_qid(qid):
                    return f"https://www.wikidata.org/wiki/{qid}"
                
                print("DEBUG ENTITY:", entity)
                print("DEBUG CLASS:", label)
                print("DEBUG PROPS:", props) 




                classified_entities.append({
                    "entity": entity,
                    "class": label,
                    "score": score,
                    "properties": props,
                    "wikidata_id": link["id"] if link else None
                })

            # 🔥 deduplicación final
            unique = {}
            for e in classified_entities:
                key = e["entity"].lower()
                if key not in unique or e["score"] > unique[key]["score"]:
                    unique[key] = e

            classified_entities = list(unique.values())

            # relaciones
            relations = self.relation_extractor.extract(text)

            # expansión ontológica
            suggested_classes = self.ontology_expander.discover_classes(text)

            results.append({
                "text": text,
                "entities": classified_entities,
                "relations": relations,
                "suggested_classes": suggested_classes
            })

        return results