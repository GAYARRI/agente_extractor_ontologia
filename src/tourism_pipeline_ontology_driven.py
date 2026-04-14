from __future__ import annotations

import hashlib
import re
import sys
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

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
from src.supervision.llm_supervisor import LLMSupervisor
from src.entities.entity_ranker import EntityRanker
from src.entities.entity_clusterer import EntityClusterer
from src.entities.entity_scorer import EntityScorer
from src.entities.global_entity_memory import GlobalEntityMemory
from src.entities.entity_graph_builder import EntityGraphBuilder
from src.tourism_property_extractor import TourismPropertyExtractor
from src.page_entity_resolver import PageEntityResolver
from src.dom_image_resolver import DOMImageResolver
from src.block_quality_scorer import BlockQualityScorer
from src.entity_evidence_builder import EntityEvidenceBuilder
from src.ontology_reasoner import OntologyReasoner

from src.entities.type_normalizer import TypeNormalizer
from src.ontology_distance import OntologyDistance
from src.ontology_taxonomy import PARENT_MAP


def normalize_text(text: str) -> str:
    if isinstance(text, list):
        text = " | ".join(str(x).strip() for x in text if x is not None and str(x).strip())
    elif text is None:
        text = ""
    else:
        text = str(text)

    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def text_hash(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()


def is_similar(a: str, b: str, threshold: float = 0.90) -> bool:
    return SequenceMatcher(None, a or "", b or "").ratio() > threshold


def fix_encoding(text: str) -> str:
    try:
        return (text or "").encode("latin1").decode("utf-8")
    except Exception:
        return text or ""


class TourismPipeline:
    def __init__(self, ontology_path, use_fewshots=False, fewshots=None, benchmark_mode=False):
        self.use_fewshots = use_fewshots
        self.fewshots = fewshots or []
        self.benchmark_mode = benchmark_mode

        self.debug = False

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

        self.type_normalizer = TypeNormalizer()
        self.ontology_distance = OntologyDistance(PARENT_MAP)

        self.ranker = EntityRanker(
            type_normalizer=self.type_normalizer,
            ontology_distance=self.ontology_distance,
        )

        self.clusterer = EntityClusterer()
        self.global_memory = GlobalEntityMemory()
        self.entity_scorer = EntityScorer()
        self.graph_builder = EntityGraphBuilder()
        self.tourism_property_extractor = TourismPropertyExtractor()
        self.page_entity_resolver = PageEntityResolver()
        self.dom_image_resolver = DOMImageResolver()
        self.block_quality_scorer = BlockQualityScorer()
        self.entity_evidence_builder = EntityEvidenceBuilder()
        self.ontology_reasoner = OntologyReasoner(self.ontology_index)

        self.edge_stopwords = {
            "de", "del", "la", "las", "el", "los", "y", "e", "en", "por",
            "para", "con", "sin", "a", "al", "un", "una", "uno", "unas",
            "unos", "si", "te", "tu", "sus", "su", "lo", "que", "como"
        }

        self.portal_category_terms = {
            "monumentos", "museos", "agenda", "cultura", "artesanía",
            "fiestas", "deporte", "ocio", "familia", "parques", "barrios",
            "compras", "gastronomía", "conciertos", "exposiciones",
            "actividades", "rutas", "mapas", "horarios", "alojamientos",
            "visitas", "planes", "contactos", "información", "informacion",
            "guías", "guias", "idioma", "moneda", "comer", "salir"
        }

        self.ui_noise_patterns = [
            "google analytics",
            "esta web utiliza",
            "te has suscrito",
            "watch later",
            "copy link",
            "share",
            "suscrito satisfactoriamente",
            "cookies",
            "privacidad",
            "aviso legal",
            "política de cookies",
            "politica de cookies",
            "páginas más populares",
            "paginas más populares",
            "número de visitantes",
            "numero de visitantes",
            "ir a página",
            "ir a pagina",
            "ver listado",
            "haz clic aquí",
            "haz clic aqui"
        ]

        self.navigation_patterns = [
            "qué hacer",
            "que hacer",
            "prepara tu viaje",
            "durante tu estancia",
            "cómo moverte",
            "como moverte",
            "ideas y planes",
            "monumentos y museos",
            "comer y salir",
            "ocio y familia",
            "de compras",
            "puntos de información turística",
            "puntos de informacion turistica"
        ]

    def _debug_stage(self, stage: str, entities):
        if not self.debug:
            return

        try:
            n = len(entities) if entities is not None else 0
        except Exception:
            n = -1

        print(f"[PIPELINE] {stage}: count={n}", file=sys.stderr)

        if not isinstance(entities, list) or not entities:
            return

        for i, sample in enumerate(entities[:3], start=1):
            print(f"[PIPELINE] {stage} sample_{i}_type={type(sample).__name__}", file=sys.stderr)

            if isinstance(sample, dict):
                name = (
                    sample.get("name")
                    or sample.get("entity_name")
                    or sample.get("entity")
                    or sample.get("label")
                    or ""
                )
                entity_class = sample.get("class", "")
                entity_type = sample.get("type", "")
                semantic_type = sample.get("semantic_type", "")
                semantic_score = sample.get("semantic_score", sample.get("semantic_similarity", ""))
                final_score = sample.get("final_score", "")
                score = sample.get("score", "")

                print(
                    f"[PIPELINE] {stage} sample_{i}="
                    f"name={name!r} | class={entity_class!r} | type={entity_type!r} | "
                    f"semantic_type={semantic_type!r} | semantic_score={semantic_score!r} | "
                    f"score={score!r} | final_score={final_score!r}",
                    file=sys.stderr
                )
            else:
                print(f"[PIPELINE] {stage} sample_{i}={sample!r}", file=sys.stderr)

    def reset_runtime_state(self):
        self.global_memory = GlobalEntityMemory()
        self.graph_builder = EntityGraphBuilder()

    def _fetch_html(self, url: str) -> str:
        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        return response.text

    def _extract_text(self, blocks: List[Any]) -> str:
        parts = []

        for block in blocks or []:
            if isinstance(block, dict):
                txt = block.get("text") or block.get("content") or block.get("html") or ""
            else:
                txt = getattr(block, "text", "") or getattr(block, "content", "") or ""
            txt = str(txt).strip()
            if txt:
                parts.append(txt)

        return "\n".join(parts)

    def _scalar_text(self, value, join_with: str = " | ") -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return join_with.join(str(x).strip() for x in value if x is not None and str(x).strip())
        if isinstance(value, tuple):
            return join_with.join(str(x).strip() for x in value if x is not None and str(x).strip())
        return str(value).strip()

    def _first_scalar(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            for v in value:
                s = str(v).strip()
                if s:
                    return s
            return ""
        if isinstance(value, tuple):
            for v in value:
                s = str(v).strip()
                if s:
                    return s
            return ""
        return str(value).strip()

    def _sanitize_entities_for_downstream(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sanitized = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)

            for field in (
                "name",
                "label",
                "entity",
                "entity_name",
                "normalized_type",
                "description",
                "short_description",
                "long_description",
            ):
                if field in item:
                    item[field] = self._scalar_text(item.get(field))

            if "class" in item:
                item["class"] = self._first_scalar(item.get("class"))

            if "type" in item and isinstance(item.get("type"), (list, tuple)):
                type_list = [str(x).strip() for x in item["type"] if x is not None and str(x).strip()]
                item["type_list"] = type_list[:]
                item["type"] = type_list[0] if type_list else ""

            if not (item.get("name") or item.get("entity_name") or item.get("entity") or item.get("label")):
                continue

            sanitized.append(item)

        return sanitized

    def _promote_semantic_type(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        promoted = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)
            semantic_type = str(item.get("semantic_type") or "").strip()

            if semantic_type:
                short_type = semantic_type.split("#")[-1].split("/")[-1].strip()

                if short_type:
                    item["class"] = short_type
                    item["type"] = short_type

            promoted.append(item)

        return promoted

    def _apply_llm_supervisor(self, ranked_entities, page_text: str, url: str):
        supervisor = self.llm_supervisor

        method_candidates = [
            "refine",
            "review",
            "supervise",
            "validate",
            "postprocess",
            "process",
            "run",
        ]

        for method_name in method_candidates:
            if not hasattr(supervisor, method_name):
                continue

            method = getattr(supervisor, method_name)

            for call in (
                lambda: method(ranked_entities, page_text=page_text, url=url, benchmark=self.benchmark_mode),
                lambda: method(ranked_entities, page_text=page_text, url=url),
                lambda: method(ranked_entities, page_text=page_text),
                lambda: method(ranked_entities),
            ):
                try:
                    return call()
                except TypeError:
                    pass

        return ranked_entities

    def _extract_page_title(self, html):
        try:
            soup = BeautifulSoup(html or "", "html.parser")
            if soup.title and soup.title.string:
                return soup.title.string.strip()
        except Exception:
            pass
        return ""

    def _extract_h1(self, html):
        try:
            soup = BeautifulSoup(html or "", "html.parser")
            h1 = soup.find("h1")
            if h1:
                return h1.get_text(" ", strip=True)
        except Exception:
            pass
        return ""

    def _extract_breadcrumb_text(self, html):
        try:
            soup = BeautifulSoup(html or "", "html.parser")
            text = soup.get_text(" ", strip=True).lower()
            if "breadcrumb" in text or "migas" in text:
                return soup.get_text(" ", strip=True)
        except Exception:
            pass
        return ""

    def _extract_url_slug(self, url):
        try:
            parsed = urlparse(url or "")
            slug = parsed.path.rstrip("/").split("/")[-1]
            slug = slug.replace("-", " ").replace("_", " ").strip().lower()
            return slug
        except Exception:
            return ""

    def _normalized_for_match(self, text):
        t = self._scalar_text(text).lower().strip()
        t = re.sub(r"[^\wáéíóúñü\s]", " ", t, flags=re.IGNORECASE)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def refine_specific_type(self, entity_name, current_label, text="", url="", html=""):
        name = self._normalized_for_match(entity_name)

        if "basilica" in name or "basílica" in name:
            return "Basilica"
        if "capilla" in name:
            return "Chapel"
        if "iglesia" in name:
            return "Church"
        if "catedral" in name:
            return "Cathedral"
        if "castillo" in name:
            return "Castle"
        if "alcazar" in name or "alcázar" in name:
            return "Alcazar"
        if "plaza" in name:
            return "Square"
        if "ayuntamiento" in name:
            return "TownHall"
        if "estadio" in name:
            return "Stadium"
        if "museo" in name:
            return "Museum"
        if "convento" in name or "monasterio" in name:
            return "TouristAttraction"

        return current_label

    def _is_contextual_noise_entity(self, entity_name):
        name = self._normalized_for_match(entity_name)
        bad_terms = [
            "maps abrir",
            "sitio web ver",
            "ver más",
            "ver mas",
            "telefono",
            "teléfono",
            "direccion",
            "dirección",
            "calle ",
            "avenida ",
            "plaza de ",
            "contacto",
            "google maps",
            "abrir en google maps",
        ]
        return any(term in name for term in bad_terms)

    def select_primary_entities(self, entities, html="", url="", top_k=3):
        if not entities:
            return []

        title = self._normalized_for_match(self._extract_page_title(html))
        h1 = self._normalized_for_match(self._extract_h1(html))
        breadcrumb = self._normalized_for_match(self._extract_breadcrumb_text(html))
        slug = self._normalized_for_match(self._extract_url_slug(url))

        scored = []

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            name = (
                entity.get("name")
                or entity.get("entity_name")
                or entity.get("entity")
                or entity.get("label")
                or ""
            )
            norm_name = self._normalized_for_match(name)

            if not norm_name:
                continue

            score = float(entity.get("score", 0) or 0)
            centrality = 0.0

            if slug and norm_name in slug:
                centrality += 4.0
            if slug and slug in norm_name:
                centrality += 3.0
            if h1 and norm_name in h1:
                centrality += 4.0
            if h1 and h1 in norm_name:
                centrality += 3.0
            if title and norm_name in title:
                centrality += 2.5
            if title and title in norm_name:
                centrality += 2.0
            if breadcrumb and norm_name in breadcrumb:
                centrality += 1.5
            if self._is_contextual_noise_entity(name):
                centrality -= 4.0

            entity["_page_centrality_score"] = round(centrality, 3)
            entity["_benchmark_rank_score"] = round(score + centrality, 3)
            scored.append(entity)

        scored.sort(
            key=lambda x: (
                x.get("_benchmark_rank_score", 0),
                x.get("_page_centrality_score", 0),
                x.get("score", 0),
            ),
            reverse=True,
        )

        return scored[:top_k]

    def run(self, html: str, url: str = "", expected_type: Optional[str] = None):
        html = self._scalar_text(html)
        if not html and url:
            html = self._fetch_html(url)

        blocks = self.block_extractor.extract(html)
        page_text = self._extract_text(blocks)

        entities = self.entity_extractor.extract(blocks)
        self._debug_stage("extract", entities)

        entities = self.cleaner.clean(entities)
        self._debug_stage("clean", entities)

        entities = self.deduplicator.deduplicate(entities)
        self._debug_stage("deduplicate", entities)

        entities = self.normalizer.normalize(entities)
        self._debug_stage("normalize", entities)

        try:
            entities = self.expander.expand(entities, page_text)
        except TypeError:
            try:
                entities = self.expander.expand(entities, text=page_text)
            except TypeError:
                pass
        self._debug_stage("expand", entities)

        entities = self.splitter.split(entities)
        self._debug_stage("split", entities)

        try:
            candidates = self.semantic_matcher.match(entities, page_text=page_text)
        except TypeError:
            candidates = self.semantic_matcher.match(entities)

        candidates = self._promote_semantic_type(candidates)
        self._debug_stage("semantic_match", candidates)

        ranked_entities = self.ranker.rank(
            candidates=candidates,
            target_type=expected_type,
            page_text=page_text,
        )

        ranked_entities = self._promote_semantic_type(ranked_entities)
        self._debug_stage("rank", ranked_entities)

        ranked_entities = self._sanitize_entities_for_downstream(ranked_entities)
        self._debug_stage("sanitize_ranked", ranked_entities)

        final_entities = self._apply_llm_supervisor(
            ranked_entities=ranked_entities,
            page_text=page_text,
            url=url,
        )
        self._debug_stage("llm_supervisor", final_entities)

        final_entities = self._sanitize_entities_for_downstream(final_entities)
        self._debug_stage("sanitize_final", final_entities)

        pre_cluster_entities = list(final_entities)

        try:
            clustered = self.clusterer.cluster(final_entities)
        except Exception:
            clustered = final_entities
        self._debug_stage("cluster", clustered)

        if (
            isinstance(clustered, list)
            and clustered
            and isinstance(clustered[0], list)
        ):
            clustered = pre_cluster_entities

        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("sanitize_flattened", clustered)

        clustered = self._enrich_final_entities(
            entities=clustered,
            html=html,
            page_text=page_text,
            url=url,
        )
        self._debug_stage("enriched_final", clustered)

        return clustered

    def _is_wikimedia_url(self, url):
        if not url:
            return False

        low = str(url).lower()
        return (
            "wikimedia.org" in low
            or "wikipedia.org" in low
            or "wikidata.org" in low
            or "commons.wikimedia.org" in low
        )

    def _safe_call_component(self, component, method_names, *args, **kwargs):
        if component is None:
            return None

        comp_name = component.__class__.__name__

        for method_name in method_names:
            if not hasattr(component, method_name):
                continue

            method = getattr(component, method_name)

            call_variants = [
                ("args", lambda: method(*args)),
                ("kwargs", lambda: method(*args, **kwargs)),
            ]

            for variant_name, call in call_variants:
                try:
                    result = call()
                    if self.debug:
                        print(f"[ENRICH] {comp_name}.{method_name} ({variant_name}) -> OK")
                    return result
                except TypeError as e:
                    if self.debug:
                        print(f"[ENRICH] {comp_name}.{method_name} ({variant_name}) -> TypeError: {e}")
                except Exception as e:
                    if self.debug:
                        print(f"[ENRICH] {comp_name}.{method_name} ({variant_name}) -> Exception: {e}")

        if self.debug:
            print(f"[ENRICH] {comp_name} -> no compatible method call worked")

        return None

    def _extract_first_description(self, entity: Dict[str, Any], page_text: str) -> Dict[str, Any]:
        result = self._safe_call_component(
            self.description_extractor,
            ["extract"],
            entity,
            page_text,
        )

        if isinstance(result, dict):
            return result

        if isinstance(result, str) and result.strip():
            text = result.strip()
            return {
                "description": text,
                "short_description": text[:220],
                "long_description": text,
            }

        return {}

    def _extract_entity_properties(self, entity: Dict[str, Any], html: str, page_text: str, url: str) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}

        result = self._safe_call_component(
            self.tourism_property_extractor,
            ["extract"],
            entity,
            page_text,
            html,
            url,
        )
        if isinstance(result, dict):
            merged.update({k: v for k, v in result.items() if v not in (None, "", [], {})})

        entity_class = str(entity.get("class") or entity.get("type") or "Thing").strip() or "Thing"
        result = self._safe_call_component(
            self.property_enricher,
            ["enrich"],
            entity,
            entity_class,
            page_text,
        )
        if isinstance(result, dict):
            merged.update({k: v for k, v in result.items() if v not in (None, "", [], {})})

        return merged

    def _extract_wikidata_id(self, entity_name: str, entity_type: str, description: str, url: str) -> str:
        result = self._safe_call_component(
            self.wikidata_linker,
            ["link", "link_entity", "resolve", "run", "process"],
            entity_name=entity_name,
            entity_class=entity_type,
            short_description=description,
            long_description=description,
            source_url=url,
        )

        if isinstance(result, str):
            return result.strip()

        if isinstance(result, dict):
            return str(
                result.get("wikidata_id")
                or result.get("id")
                or result.get("qid")
                or ""
            ).strip()

        return ""

    def _extract_entity_image(self, entity_name: str, html: str, url: str, block_text: str = "") -> str:
        img = ""

        result = self._safe_call_component(
            self.dom_image_resolver,
            ["resolve_with_score"],
            html=html,
            entity_name=entity_name,
            base_url=url,
            block_text=block_text,
            min_score=0,
        )

        if isinstance(result, tuple) and result:
            img = str(result[0] or "").strip()

        if not img:
            result = self._safe_call_component(
                self.dom_image_resolver,
                ["resolve", "resolve_image_for_entity"],
                html=html,
                entity_name=entity_name,
                base_url=url,
                block_text=block_text,
                min_score=0,
            )

            if isinstance(result, str):
                img = result.strip()

        return img

    def _extract_coordinates_from_props(self, props: Dict[str, Any]) -> Dict[str, Any]:
        lat = None
        lng = None

        def _to_float(v):
            try:
                if v is None or v == "":
                    return None
                return float(v)
            except Exception:
                return None

        if isinstance(props, dict):
            lat = _to_float(props.get("latitude"))
            lng = _to_float(props.get("longitude"))

            if lng is None:
                lng = _to_float(props.get("lon"))

            coords = props.get("coordinates")
            if isinstance(coords, dict):
                if lat is None:
                    lat = _to_float(coords.get("lat"))
                if lng is None:
                    lng = _to_float(coords.get("lng") or coords.get("lon"))

        if lat is not None and not (-90 <= lat <= 90):
            lat = None
        if lng is not None and not (-180 <= lng <= 180):
            lng = None

        return {"lat": lat, "lng": lng}

    def _build_enriched_entity(self, entity: Dict[str, Any], html: str, page_text: str, url: str) -> Dict[str, Any]:
        item = dict(entity)

        name = (
            item.get("name")
            or item.get("entity_name")
            or item.get("entity")
            or item.get("label")
            or ""
        ).strip()

        entity_type = str(item.get("class") or item.get("type") or "Thing").strip() or "Thing"

        description_data = self._extract_first_description(
            entity=item,
            page_text=page_text,
        )

        description_text = (
            str(description_data.get("description") or "").strip()
            or str(description_data.get("short_description") or "").strip()
            or str(description_data.get("long_description") or "").strip()
        )

        props = self._extract_entity_properties(
            entity=item,
            html=html,
            page_text=page_text,
            url=url,
        )

        wikidata_id = self._extract_wikidata_id(
            entity_name=name,
            entity_type=entity_type,
            description=description_text,
            url=url,
        )

        image = self._extract_entity_image(
            entity_name=name,
            html=html,
            url=url,
            block_text=page_text[:1000],
        )

        coordinates = self._extract_coordinates_from_props(props)

        if self.debug:
            print(f"[ENRICH] entity={name!r}")
            print(f"[ENRICH] description_data={description_data!r}")
            print(f"[ENRICH] props={props!r}")
            print(f"[ENRICH] wikidata_id={wikidata_id!r}")
            print(f"[ENRICH] image={image!r}")
            print(f"[ENRICH] coordinates={coordinates!r}")

        if image:
            item["image"] = image
            item["mainImage"] = image

        if description_data:
            for k, v in description_data.items():
                if v not in (None, "", [], {}):
                    item[k] = v

        if description_text and not item.get("description"):
            item["description"] = description_text

        if wikidata_id:
            item["wikidata_id"] = wikidata_id

        if props:
            existing_props = item.get("properties")
            if not isinstance(existing_props, dict):
                existing_props = {}
            existing_props.update(props)
            item["properties"] = existing_props

        item["coordinates"] = coordinates

        if coordinates.get("lat") is not None:
            item["latitude"] = coordinates["lat"]
        if coordinates.get("lng") is not None:
            item["longitude"] = coordinates["lng"]

        item["sourceUrl"] = item.get("sourceUrl") or url

        return item

    def _enrich_final_entities(self, entities: List[Dict[str, Any]], html: str, page_text: str, url: str) -> List[Dict[str, Any]]:
        enriched = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            try:
                enriched_entity = self._build_enriched_entity(
                    entity=entity,
                    html=html,
                    page_text=page_text,
                    url=url,
                )
            except Exception:
                enriched_entity = dict(entity)

            enriched.append(enriched_entity)

        return enriched