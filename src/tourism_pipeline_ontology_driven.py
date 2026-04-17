from __future__ import annotations

import hashlib
import re
import sys
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from entity_processing.postprocess import postprocess_entities

import requests
from bs4 import BeautifulSoup

from src.html_block_extractor import HTMLBlockExtractor
from src.tourism_entity_extractor import TourismEntityExtractor
from src.entity_cleaner import EntityCleaner
from src.entity_filter import EntityFilter
from src.entity_quality_scorer import EntityQualityScorer
from src.entity_type_resolver import EntityTypeResolver
from src.ontology_matcher import OntologyMatcher
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
from src.entities.entity_final_filter import EntityFinalFilter

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

        self.enable_entity_postprocess = False
        self.enable_entity_dedupe = True
        self.debug = True

        self.block_extractor = HTMLBlockExtractor()
        self.entity_extractor = TourismEntityExtractor()
        self.cleaner = EntityCleaner()
        self.entity_filter = EntityFilter()
        self.quality_scorer = EntityQualityScorer()
        self.type_resolver = EntityTypeResolver()
        self.deduplicator = EntityDeduplicator()
        self.normalizer = EntityNormalizer()
        self.expander = EntityExpander()
        self.splitter = EntitySplitter()
        self.ontology_index = OntologyIndex(ontology_path)
        self.ontology_matcher = OntologyMatcher(self.ontology_index)
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
        self.final_filter = EntityFinalFilter()
        self.tourism_property_extractor = TourismPropertyExtractor()
        self.page_entity_resolver = PageEntityResolver()
        self.dom_image_resolver = DOMImageResolver()
        self.block_quality_scorer = BlockQualityScorer()
        self.entity_evidence_builder = EntityEvidenceBuilder()
        self.ontology_reasoner = OntologyReasoner(self.ontology_index)

        self.edge_stopwords = {
            "de", "del", "la", "las", "el", "los", "y", "e", "en", "por",
            "para", "con", "sin", "a", "al", "un", "una", "uno", "unas",
            "unos", "si", "te", "tu", "sus", "su", "lo", "que", "como",
            "ver", "más", "mas"
        }

        self.portal_category_terms = {
            "monumentos", "museos", "agenda", "cultura", "artesanía",
            "artesania", "fiestas", "deporte", "ocio", "familia", "parques",
            "barrios", "compras", "gastronomía", "gastronomia", "conciertos",
            "exposiciones", "actividades", "rutas", "mapas", "horarios",
            "alojamientos", "visitas", "planes", "contactos", "información",
            "informacion", "guías", "guias", "idioma", "moneda", "comer",
            "salir", "lugares", "eventos", "hoteles", "albergues", "pensiones",
            "mercados", "excursiones", "senderismo", "cicloturismo"
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
            "haz clic aqui",
            "facebook instagram",
            "consignas mapas"
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
            "puntos de informacion turistica",
            "todos los lugares",
            "lugares de interés",
            "lugares de interes",
            "museos y centros de interpretación",
            "museos y centros de interpretacion",
            "visitas guiadas",
            "dónde alojarse",
            "donde alojarse",
            "dónde comer",
            "donde comer",
        ]

        self.generic_prefix_terms = {
            "hotel", "hoteles", "hostel", "hostales", "albergue", "albergues",
            "museo", "museos", "mercado", "mercados", "festival", "festivales",
            "monasterio", "monasterios", "palacio", "palacios", "parque",
            "parques", "plaza", "plazas", "iglesia", "iglesias", "catedral",
            "catedrales", "centro", "centros", "excursiones", "visitas",
            "lugares", "monumentos"
        }

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
                "semantic_type",
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

    def _is_forbidden_type(self, value: str) -> bool:
        short = str(value or "").split("#")[-1].split("/")[-1].strip()
        return short.lower() in {"", "thing", "unknown", "entity", "item"}

    def _promote_semantic_type(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        promoted = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)
            semantic_type = str(item.get("semantic_type") or "").strip()

            if semantic_type:
                short_type = semantic_type.split("#")[-1].split("/")[-1].strip()

                if short_type and not self._is_forbidden_type(short_type):
                    item["class"] = short_type
                    item["type"] = short_type
                elif short_type:
                    item["semantic_type"] = ""
                    item["semantic_type_rejected"] = short_type

            promoted.append(item)

        return promoted

    def _normalized_for_match(self, text):
        t = self._scalar_text(text).lower().strip()
        t = re.sub(r"[^\wáéíóúñü\s]", " ", t, flags=re.IGNORECASE)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _canonical_key(self, text: str) -> str:
        t = self._normalized_for_match(text)
        t = re.sub(r"\b(ver|más|mas|si|no)\b", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _tokenize_name(self, text: str) -> List[str]:
        return [t for t in re.split(r"[^\wáéíóúñü]+", self._normalized_for_match(text)) if t]

    def _extract_url_path_tokens(self, url: str) -> List[str]:
        try:
            path = urlparse(url or "").path.lower()
        except Exception:
            return []
        return [t for t in re.split(r"[^\wáéíóúñü]+", path) if t]

    def _is_listing_like_page(self, page_signals: Optional[Dict[str, Any]] = None, page_text: str = "", url: str = "") -> bool:
        page_signals = page_signals or {}
        title = self._canonical_key(page_signals.get("title") or "")
        h1 = self._canonical_key(page_signals.get("h1") or "")
        breadcrumb = self._canonical_key(page_signals.get("breadcrumb") or "")
        slug = self._canonical_key(page_signals.get("slug") or "")
        text = self._canonical_key(page_text[:1500])

        combined = " | ".join(x for x in [title, h1, breadcrumb, slug, text] if x)

        list_indicators = [
            "todos los lugares",
            "lugares de interés",
            "lugares de interes",
            "qué ver",
            "que ver",
            "qué hacer",
            "que hacer",
            "dónde alojarse",
            "donde alojarse",
            "dónde comer",
            "donde comer",
            "tipo lugar",
            "category",
            "blog",
            "page 2",
            "page 3",
            "page 4",
            "page 5",
            "eventos",
            "lugares",
            "restaurantes",
            "hoteles",
            "pensiones",
            "albergues",
            "museos",
            "mercados",
            "visitas guiadas",
            "excursiones desde pamplona",
            "senderismo",
            "cicloturismo",
        ]

        if any(ind in combined for ind in list_indicators):
            return True

        path_tokens = set(self._extract_url_path_tokens(url))
        if path_tokens.intersection({"tipo", "lugar", "category", "blog", "page", "eventos", "lugares"}):
            return True

        return False

    def _looks_like_ui_or_category_name(self, entity_name: str) -> bool:
        key = self._canonical_key(entity_name)
        if not key:
            return True

        if key in self.portal_category_terms:
            return True

        if any(pat in key for pat in self.ui_noise_patterns):
            return True

        if any(pat in key for pat in self.navigation_patterns):
            return True

        return False

    def _looks_like_bad_compound_entity(self, entity_name: str) -> bool:
        key = self._canonical_key(entity_name)
        words = key.split()

        if not words:
            return True

        if re.search(r"\b(ver|más|mas|si)\b", key):
            return True

        generic_terms = {
            "hotel", "hoteles", "hostel", "hostales", "albergue", "albergues",
            "museo", "museos", "mercado", "mercados", "festival", "festivales",
            "excursiones", "visitas", "lugares", "monumentos", "catedral",
            "catedrales", "plaza", "plazas", "parque", "parques", "turismo",
            "gastronomia", "gastronomía", "mapas", "familias"
        }

        hits = sum(1 for w in words if w in generic_terms)

        if len(words) >= 4 and hits >= 2:
            return True

        if len(words) >= 6 and hits >= 1:
            return True

        if len(words) >= 8:
            return True

        return False    

    def _entity_name_penalty(self, entity_name: str, url: str = "", page_signals: Optional[Dict[str, Any]] = None) -> float:
        key = self._canonical_key(entity_name)
        penalty = 0.0

        if not key:
            return 10.0

        words = key.split()

        if len(words) == 1:
            penalty += 2.0

        if self._looks_like_ui_or_category_name(key):
            penalty += 8.0

        if self._looks_like_bad_compound_entity(key):
            penalty += 8.0

        if re.search(r"\b(ver|más|mas|si)\b", key):
            penalty += 5.0

        generic_hits = sum(1 for w in words if w in self.portal_category_terms)
        if generic_hits >= 2:
            penalty += 4.0

        path_tokens = set(self._extract_url_path_tokens(url))
        if path_tokens.intersection({"tipo", "lugar", "category", "blog", "page"}):
            penalty += 2.0

        return penalty    

    def _guess_type_from_name_and_context(self, entity_name: str, page_text: str = "", current_type: str = "") -> str:
        name = self._normalized_for_match(entity_name)
        context = self._normalized_for_match(page_text)

        monument_context_terms = [
            "estatua", "escultura", "monumento", "busto",
            "glorieta", "conjunto escultorico", "conjunto escultórico",
            "homenaje a", "dedicado a", "obra de", "escultor",
            "figura de bronce", "escultorico", "escultórico"
        ]

        event_terms = [
            "bienal", "festival", "feria", "semana santa",
            "procesion", "procesión", "congreso", "ciclo"
        ]

        place_prefixes = [
            "plaza ", "calle ", "avenida ", "parque ", "jardin ", "jardín ",
            "mercado ", "paseo ", "barrio ", "puerta ", "glorieta "
        ]

        monument_prefixes = [
            "basilica ", "basílica ", "catedral ", "iglesia ", "capilla ",
            "palacio ", "alcazar ", "alcázar ", "torre ", "puente ",
            "monasterio ", "convento "
        ]

        if any(term in name for term in event_terms):
            return "Event"

        if any(name.startswith(prefix) for prefix in place_prefixes):
            return "Place"

        if any(name.startswith(prefix) for prefix in monument_prefixes):
            return "Monument"

        if any(term in context for term in monument_context_terms):
            return "Monument"

        if any(k in name for k in ["flamenco", "arte", "folklore", "folclore", "tradicion", "tradición", "cultura"]):
            return "Concept"

        return current_type or ""

    wikidata_hint = ""

    def _ensure_entity_type(
        self,
        entities: List[Dict[str, Any]],
        page_text: str = "",
        page_signals: Optional[Dict[str, Any]] = None,
        expected_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        fixed = []
        weak_types = {"", "thing", "unknown", "entity", "item"}
        forbidden_final_types = {"thing"}

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)
            current_class = str(item.get("class") or "").strip()
            current_type = str(item.get("type") or "").strip()
            semantic_type = str(item.get("semantic_type") or "").strip()
            props = item.get("properties") if isinstance(item.get("properties"), dict) else {}
            prop_type = str(props.get("type") or "").strip()

            def normalize_candidate_type(value: str) -> str:
                value = str(value or "").strip()
                if not value:
                    return ""
                short = value.split("#")[-1].split("/")[-1].strip()
                if short.lower() in weak_types:
                    return ""
                return short

            normalized_class = normalize_candidate_type(current_class)
            normalized_type = normalize_candidate_type(current_type)
            normalized_semantic = normalize_candidate_type(semantic_type)
            normalized_prop_type = normalize_candidate_type(prop_type)
            canonical_type = normalized_class or normalized_type or normalized_semantic or normalized_prop_type

            name = item.get("name") or item.get("entity_name") or item.get("entity") or item.get("label") or ""
            wikidata_hint = self._guess_wikidata_class_hint(entity_name=name, page_text=page_text)

            if canonical_type and canonical_type.lower() not in weak_types and canonical_type.lower() not in forbidden_final_types:
                item["class"] = canonical_type
                item["type"] = canonical_type
                if wikidata_hint:
                    item["wikidata_class_hint"] = wikidata_hint
                fixed.append(item)
                continue

            if canonical_type and canonical_type.lower() in forbidden_final_types:
                item["rejected_type"] = canonical_type


            name_norm = self._normalized_for_match(name)

            direct_name_overrides = {
                "parque fluvial": "Place",
                "navarra arena": "Place",
                "café iruña": "FoodEstablishment",
                "cafe iruña": "FoodEstablishment",
                "cafe iruna": "FoodEstablishment",
                "fundación miguel servet": "Organisation",
                "fundacion miguel servet": "Organisation",
                "clínica universitaria": "MedicalClinic",
                "clinica universitaria": "MedicalClinic",
            }

            forced_applied = False

        for k, forced_type in direct_name_overrides.items():
            if k in name_norm:
                item["class"] = forced_type
                item["type"] = forced_type
                if wikidata_hint:
                    item["wikidata_class_hint"] = wikidata_hint
                fixed.append(item)
                forced_applied = True
                break

            if forced_applied:
                continue

            if name_norm.startswith("iglesia "):
                item["class"] = "Church"
                item["type"] = "Church"
                if wikidata_hint:
                    item["wikidata_class_hint"] = wikidata_hint
                fixed.append(item)
                continue

            if name_norm.startswith("catedral "):
                item["class"] = "Cathedral"
                item["type"] = "Cathedral"
                if wikidata_hint:
                    item["wikidata_class_hint"] = wikidata_hint
                fixed.append(item)
                continue

            ontology_candidates = item.get("ontology_candidates") or []
            resolved = self.type_resolver.resolve(
                mention=name,
                context=item.get("context") or page_text,
                block_text=item.get("source_text") or "",
                page_signals=page_signals or {},
                properties=item,
                expected_type=expected_type,
                ontology_candidates=ontology_candidates,
            )

            resolved_class = str(resolved.get("class") or "Unknown").strip()
            item["type_resolution"] = resolved

            if resolved_class.lower() in weak_types or resolved_class.lower() in forbidden_final_types:
                if resolved_class.lower() in forbidden_final_types:
                    item["rejected_type"] = resolved_class
                item["class"] = "Unknown"
                item["type"] = "Unknown"
            else:
                item["class"] = resolved_class
                item["type"] = resolved_class

            if wikidata_hint:
                item["wikidata_class_hint"] = wikidata_hint

            fixed.append(item)

            return fixed

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
        if name.startswith("iglesia "):
            return "Church"
        if name.startswith("catedral "):
            return "Cathedral"

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
            "facebook instagram",
            "familias si",
            "consignas mapas",
        ]
        return any(term in name for term in bad_terms)

    def select_primary_entities(self, entities, html="", url="", top_k=3):
        if not entities:
            return []

        title = self._normalized_for_match(self._extract_page_title(html))
        h1 = self._normalized_for_match(self._extract_h1(html))
        breadcrumb = self._normalized_for_match(self._extract_breadcrumb_text(html))
        slug = self._normalized_for_match(self._extract_url_slug(url))
        page_signals = self._build_page_signals(html=html, url=url)
        listing_like = self._is_listing_like_page(page_signals=page_signals, page_text=(h1 + " " + title), url=url)

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

            penalty = self._entity_name_penalty(name, url=url, page_signals=page_signals)
            if listing_like:
                penalty += 2.0

            entity["_page_centrality_score"] = round(centrality, 3)
            entity["_name_penalty"] = round(penalty, 3)
            entity["_benchmark_rank_score"] = round(score + centrality - penalty, 3)
            scored.append(entity)

        scored.sort(
            key=lambda x: (
                x.get("_benchmark_rank_score", 0),
                x.get("_page_centrality_score", 0),
                x.get("score", 0),
            ),
            reverse=True,
        )

        selected = []
        for item in scored:
            if len(selected) >= top_k:
                break
            if float(item.get("_name_penalty", 0) or 0) >= 6:
                continue
            selected.append(item)

        return selected or scored[:top_k]

    def _build_page_signals(self, html: str = "", url: str = "") -> Dict[str, Any]:
        slug = self._extract_url_slug(url)
        return {
            "title": self._extract_page_title(html),
            "h1": self._extract_h1(html),
            "breadcrumb": self._extract_breadcrumb_text(html),
            "slug": slug,
            "slug_tokens": [t for t in re.split(r"[^\wáéíóúñü]+", (slug or "").lower()) if t],
            "url": url or "",
        }

    def _get_entity_context(self, entity: Dict[str, Any], page_text: str = "") -> str:
        parts = [
            entity.get("context") or "",
            entity.get("source_text") or "",
            entity.get("short_description") or "",
            entity.get("long_description") or "",
        ]
        context = " ".join(str(x).strip() for x in parts if str(x).strip())
        return context or page_text

    def _apply_conservative_filter(
        self,
        entities,
        page_text: str = "",
        page_signals: Optional[Dict[str, Any]] = None,
        expected_type: Optional[str] = None,
    ):
        def context_getter(item):
            return self._get_entity_context(item, page_text=page_text)

        kept, rejected = self.entity_filter.filter(
            entities=entities,
            context_getter=context_getter,
            page_signals=page_signals or {},
            expected_type=expected_type,
        )

        for item in rejected:
            item["discarded_by_filter"] = True

        return kept

    def _attach_ontology_candidates(self, entities, page_text: str = "", expected_type: Optional[str] = None):
        enriched = []
        for entity in entities or []:
            if not isinstance(entity, dict):
                continue
            item = dict(entity)
            name = item.get("name") or item.get("entity_name") or item.get("entity") or item.get("label") or ""
            context = self._get_entity_context(item, page_text=page_text)
            evidence_score = float((item.get("filter_audit") or {}).get("score") or 0.0)
            matches = self.ontology_matcher.match(
                name,
                context=context,
                expected_type=expected_type,
                evidence_score=evidence_score,
            )
            item["ontology_candidates"] = matches
            if matches:
                item["ontology_match"] = matches[0]
                item["ontology_score"] = matches[0].get("score")
            enriched.append(item)
        return enriched

    def _apply_quality_gate(self, entities, page_signals: Optional[Dict[str, Any]] = None, url: str = ""):
        gated = []
        for entity in entities or []:
            if not isinstance(entity, dict):
                continue
            item = dict(entity)
            quality = self.quality_scorer.evaluate(item, page_url=url, page_signals=page_signals or {})
            item["quality_audit"] = quality
            if quality.get("decision") == "discard":
                continue
            item["evidence_score"] = quality.get("score", 0.0)
            gated.append(item)
        return gated

    def run(self, html: str, url: str = "", expected_type: Optional[str] = None):
        html = self._scalar_text(html)
        if not html and url:
            html = self._fetch_html(url)

        blocks = self.block_extractor.extract(html)
        page_text = self._extract_text(blocks)
        page_signals = self._build_page_signals(html=html, url=url)
        strict_listing_page = self._is_strict_listing_page(
            page_signals=page_signals,
            page_text=page_text,
            url=url,
        )

        if strict_listing_page:
            if self.debug:
                print(f"[PIPELINE] strict_listing_page -> skipping entity extraction for {url}", file=sys.stderr)
            return [] 

        listing_like_page = self._is_listing_like_page(page_signals=page_signals, page_text=page_text, url=url)

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

        split_entities = list(entities or [])

        entities = self._apply_conservative_filter(
            split_entities,
            page_text=page_text,
            page_signals=page_signals,
            expected_type=expected_type,
        )

        if not entities and split_entities and not strict_listing_page:
            if self.debug:
                print(
                    f"[PIPELINE] conservative_filter_bypassed_on_empty for {url}: "
                    f"split={len(split_entities)}",
                    file=sys.stderr,
                )
            entities = split_entities

        self._debug_stage("conservative_filter", entities)

        entities = self._attach_ontology_candidates(entities, page_text=page_text, expected_type=expected_type)
        entities = self._ensure_entity_type(
            entities,
            page_text=page_text,
            page_signals=page_signals,
            expected_type=expected_type,
        )
        self._debug_stage("typed_candidates", entities)

        try:
            candidates = self.semantic_matcher.match(entities, page_text=page_text)
        except TypeError:
            candidates = self.semantic_matcher.match(entities)

        candidates = self._promote_semantic_type(candidates)
        candidates = self._ensure_entity_type(
            candidates,
            page_text=page_text,
            page_signals=page_signals,
            expected_type=expected_type,
        )
        candidates = self._apply_quality_gate(candidates, page_signals=page_signals, url=url)
        self._debug_stage("semantic_match", candidates)

        ranked_entities = self.ranker.rank(
            candidates=candidates,
            target_type=expected_type,
            page_text=page_text,
        )

        ranked_entities = self._promote_semantic_type(ranked_entities)
        ranked_entities = self._ensure_entity_type(
            ranked_entities,
            page_text=page_text,
            page_signals=page_signals,
            expected_type=expected_type,
        )
        ranked_entities = self._apply_quality_gate(ranked_entities, page_signals=page_signals, url=url)
        self._debug_stage("rank", ranked_entities)

        if listing_like_page:
            top_k = 3
        else:
            top_k = max(3, min(8, len(ranked_entities) or 3))

        ranked_entities = self.select_primary_entities(
            ranked_entities,
            html=html,
            url=url,
            top_k=top_k,
        )
        ranked_entities = self._sanitize_entities_for_downstream(ranked_entities)
        self._debug_stage("sanitize_ranked", ranked_entities)

        final_entities = self._apply_llm_supervisor(
            ranked_entities=ranked_entities,
            page_text=page_text,
            url=url,
        )
        self._debug_stage("llm_supervisor", final_entities)

        final_entities = self._sanitize_entities_for_downstream(final_entities)
        final_entities = self._ensure_entity_type(
            final_entities,
            page_text=page_text,
            page_signals=page_signals,
            expected_type=expected_type,
        )
        final_entities = self._apply_quality_gate(final_entities, page_signals=page_signals, url=url)
        self._debug_stage("sanitize_final", final_entities)

        pre_cluster_entities = list(final_entities)

        clustered = pre_cluster_entities
        try:
            maybe_clustered = self.clusterer.cluster(final_entities)
            if isinstance(maybe_clustered, list) and maybe_clustered:
                if isinstance(maybe_clustered[0], list):
                    clustered = pre_cluster_entities
                else:
                    clustered = maybe_clustered
            elif isinstance(maybe_clustered, list):
                clustered = []
        except Exception:
            clustered = pre_cluster_entities

        self._debug_stage("cluster", clustered)

        clustered = self._sanitize_entities_for_downstream(clustered)
        clustered = self._ensure_entity_type(
            clustered,
            page_text=page_text,
            page_signals=page_signals,
            expected_type=expected_type,
        )
        clustered = self._apply_quality_gate(clustered, page_signals=page_signals, url=url)
        self._debug_stage("sanitize_flattened", clustered)

        clustered = self._enrich_final_entities(
            entities=clustered,
            html=html,
            page_text=page_text,
            url=url,
        )
        self._debug_stage("enriched_final", clustered)

        clustered = self._apply_final_filter(
            clustered,
            page_signals=page_signals,
            page_text=page_text,
            url=url,
            listing_like_page=listing_like_page,
        )
        self._debug_stage("final_filter", clustered)

        if self.enable_entity_postprocess:
            try:
                clustered = postprocess_entities(
                    clustered,
                    enable_dedupe=self.enable_entity_dedupe,
                )
                self._debug_stage("postprocessed_final", clustered)
            except Exception as e:
                if self.debug:
                    print(f"[POSTPROCESS] failed: {e}", file=sys.stderr)

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

        entity_class = str(entity.get("class") or entity.get("type") or "").strip() or "Unknown"
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

        entity_type = str(item.get("class") or item.get("type") or "").strip()

        if entity_type.lower() in {"", "thing", "unknown", "entity", "item"}:
            guessed = self._guess_type_from_name_and_context(
                entity_name=name,
                page_text=page_text,
                current_type="",
            )
            entity_type = guessed or "Unknown"
            item["class"] = entity_type
            item["type"] = entity_type

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

        wikidata_entity_type = str(item.get("wikidata_class_hint") or entity_type).strip()

        wikidata_id = self._extract_wikidata_id(
            entity_name=name,
            entity_type=wikidata_entity_type,
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
            print(f"[ENRICH] entity_type={entity_type!r}")
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

            prop_type = str(existing_props.get("type") or "").strip()
            if prop_type and not str(item.get("class") or "").strip():
                item["class"] = prop_type
            if prop_type and not str(item.get("type") or "").strip():
                item["type"] = prop_type

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

    def _guess_wikidata_class_hint(self, entity_name: str, page_text: str = "") -> str:
        name = self._normalized_for_match(entity_name)
        context = self._normalized_for_match(page_text)

        monument_context_terms = [
            "estatua", "escultura", "monumento", "busto",
            "conjunto escultorico", "conjunto escultórico",
            "homenaje a", "dedicado a", "obra de", "escultor"
        ]

        if any(term in context for term in monument_context_terms):
            return "monument"

        person_terms = [
            "nacio", "nació", "murio", "murió", "poeta", "pintor",
            "escultor", "torero", "cantante", "cantaor",
            "bailaor", "escritor", "compositor", "artista"
        ]

        if any(term in context for term in person_terms):
            return "person"

        if any(k in name for k in ["bienal", "festival", "feria", "semana santa"]):
            return "event"

        if any(name.startswith(prefix) for prefix in ["plaza ", "calle ", "avenida ", "parque ", "mercado ", "barrio "]):
            return "place"

        return ""

    def _apply_final_filter(
        self,
        entities,
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
        listing_like_page: bool = False,
    ):
        prekept = []
        prerejected = []

        for item in entities or []:
            if not isinstance(item, dict):
                continue

            name = (
                item.get("name")
                or item.get("entity_name")
                or item.get("entity")
                or item.get("label")
                or ""
            )

            reasons = []
            penalty = self._entity_name_penalty(name, url=url, page_signals=page_signals)

            if self._looks_like_ui_or_category_name(name):
                reasons.append("ui_or_category_name")
            if self._looks_like_bad_compound_entity(name):
                reasons.append("bad_compound_name")
            if self._is_contextual_noise_entity(name):
                reasons.append("contextual_noise_name")

            if listing_like_page and len(self._tokenize_name(name)) >= 5:
                reasons.append("listing_page_long_compound")

            if penalty >= 5 or reasons:
                rejected = dict(item)
                rejected["discarded_by_final_filter"] = True
                audit = rejected.get("final_filter_audit") or {}
                if not isinstance(audit, dict):
                    audit = {}
                old_reasons = audit.get("reasons") or []
                audit["reasons"] = sorted(set(list(old_reasons) + reasons))
                rejected["final_filter_audit"] = audit
                prerejected.append(rejected)
                entity_type = str(item.get("class") or item.get("type") or "").strip().lower()
                if entity_type in {"unknown", ""} and penalty >= 3:
                    reasons.append("weak_type_and_bad_name")

            else:
                prekept.append(item)

        kept, rejected = self.final_filter.filter(prekept)

        for item in rejected:
            item["discarded_by_final_filter"] = True

        rejected = prerejected + rejected

        if self.debug:
            print(
                f"[PIPELINE] final_filter kept={len(kept)} rejected={len(rejected)}",
                file=sys.stderr,
            )
            for i, sample in enumerate(rejected[:5], start=1):
                try:
                    print(
                        f"[PIPELINE] final_filter rejected_{i}="
                        f"name={sample.get('name')!r} "
                        f"reasons={((sample.get('final_filter_audit') or {}).get('reasons') or [])}",
                        file=sys.stderr,
                    )
                except Exception:
                    pass

        return kept
    def _is_strict_listing_page(self, page_signals: Optional[Dict[str, Any]] = None, page_text: str = "", url: str = "") -> bool:
        page_signals = page_signals or {}

        title = self._canonical_key(page_signals.get("title") or "")
        h1 = self._canonical_key(page_signals.get("h1") or "")
        breadcrumb = self._canonical_key(page_signals.get("breadcrumb") or "")
        slug = self._canonical_key(page_signals.get("slug") or "")
        head_text = self._canonical_key(page_text[:1800])

        combined = " | ".join(x for x in [title, h1, breadcrumb, slug, head_text] if x)

        strong_patterns = [
            "todos los lugares",
            "qué hacer", "que hacer",
            "qué ver", "que ver",
            "dónde alojarse", "donde alojarse",
            "dónde comer", "donde comer",
            "lugares de interés", "lugares de interes",
            "museos y centros de interpretación",
            "museos y centros de interpretacion",
            "visitas guiadas",
            "excursiones desde pamplona",
            "pensiones y hostales",
            "agroturismos",
            "areas de autocaravanas",
            "tipo lugar",
        ]

        if any(p in combined for p in strong_patterns):
            return True

        path_tokens = set(self._extract_url_path_tokens(url))
        if path_tokens.intersection({"tipo", "lugar", "category", "blog", "page"}):
            return True

        return False