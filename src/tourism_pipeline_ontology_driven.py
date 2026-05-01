from __future__ import annotations

import hashlib
import re
import sys
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from entity_processing.postprocess import postprocess_entities

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
from src.kg_postprocessor import KGPostProcessor
from src.nominatim_resolver import HybridGeoResolver
from src.entities.type_normalizer import TypeNormalizer
from src.ontology_distance import OntologyDistance
from src.ontology_taxonomy import PARENT_MAP

from src.ontology_utils import (
    extract_ontology_catalog,
    load_valid_classes_from_ontology,
    enforce_closed_world_batch,
    choose_route_like_class,
    choose_event_class,
)

try:
    from src.tourism_evidence_score import TourismEvidenceScore
except Exception:
    TourismEvidenceScore = None


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


def strip_sitewide_footer_text(text: str) -> str:
    value = "" if text is None else str(text)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"^\s*ir al contenido\s+", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"^\s*reserva tu actividad\s+", "", value, flags=re.IGNORECASE).strip()
    low = value.lower()
    cut_points = []

    for marker in [
        "ayuntamiento de pamplona 31001",
        "descubre pamplona",
        "© 2025 ayuntamiento de pamplona",
    ]:
        idx = low.find(marker)
        if idx > 0:
            cut_points.append(idx)

    if cut_points:
        value = value[: min(cut_points)].strip()

    return value


def text_hash(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()


def is_similar(a: str, b: str, threshold: float = 0.90) -> bool:
    return SequenceMatcher(None, a or "", b or "").ratio() > threshold


def fix_encoding(text: str) -> str:
    try:
        return (text or "").encode("latin1").decode("utf-8")
    except Exception:
        return text or ""


def compact_entity_description(text: str, entity_name: str = "") -> str:
    value = strip_sitewide_footer_text(text or "")
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return ""

    if entity_name:
        escaped_name = re.escape(str(entity_name).strip())
        if escaped_name:
            value = re.sub(
                rf"^(?:{escaped_name}\s+){{2,}}",
                f"{entity_name} ",
                value,
                flags=re.IGNORECASE,
            ).strip()
            value = re.sub(
                rf"\b({escaped_name})(?:\s+\1){{1,}}",
                r"\1",
                value,
                flags=re.IGNORECASE,
            ).strip()

    value = re.sub(r"\b(compartir|guardar favorito|eliminar favorito|ir a mis favoritos)\b.*$", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\b(qu[eé]\s+hacer|planes\s+para\s+inspirarte)\b.*$", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s+", " ", value).strip(" -|,;:")
    return value


class TourismPipeline:
    def __init__(
        self,
        ontology_path: str,
        llm=None,
        entity_extractor=None,
        block_extractor=None,
        type_resolver=None,
        kg_postprocessor=None,
        use_fewshots: bool = False,
        benchmark_mode: bool = False,
        **kwargs,
    ):
        self.ontology_path = ontology_path
        self.llm = llm
        self.use_fewshots = use_fewshots
        self.benchmark_mode = benchmark_mode
        self.debug = kwargs.get("debug", False)

        def _safe_build(factory, *args, default=None, **kws):
            try:
                return factory(*args, **kws)
            except TypeError:
                try:
                    return factory()
                except Exception:
                    return default
            except Exception:
                return default

        try:
            from src.block_extractor import BlockExtractor
            self.block_extractor = block_extractor or BlockExtractor()
        except Exception:
            self.block_extractor = block_extractor or HTMLBlockExtractor()

        self.entity_extractor = entity_extractor or _safe_build(
            TourismEntityExtractor,
            use_spacy=False,
            default=TourismEntityExtractor(),
        )

        self.type_resolver = type_resolver or _safe_build(
            EntityTypeResolver,
            default=None,
        )

        self.kg_postprocessor = kg_postprocessor or _safe_build(
            KGPostProcessor,
            default=None,
        )

        self.tourism_evidence = _safe_build(
            TourismEvidenceScore,
            default=None,
        ) if TourismEvidenceScore else None

        self.ontology = None
        self.ontology_catalog = extract_ontology_catalog(ontology_path)
        self.ontology_index = self.ontology_catalog
        self.valid_classes = set(self.ontology_catalog.keys())
        print(f"[ONTOLOGY] Clases válidas cargadas: {len(self.valid_classes)}")

        self.cleaner = _safe_build(EntityCleaner, default=None)
        self.deduplicator = _safe_build(EntityDeduplicator, default=None)
        self.normalizer = _safe_build(EntityNormalizer, default=None)
        self.expander = _safe_build(EntityExpander, default=None)
        self.splitter = _safe_build(EntitySplitter, default=None)

        self.entity_filter = _safe_build(EntityFilter, default=None)
        self.quality_scorer = _safe_build(EntityQualityScorer, default=None)

        self.ontology_matcher = _safe_build(
            OntologyMatcher,
            self.ontology_catalog,
            default=None,
        )
        if self.ontology_matcher is None:
            self.ontology_matcher = _safe_build(OntologyMatcher, default=None)

        self.semantic_matcher = _safe_build(SemanticSimilarityMatcher, default=None)
        self.ranker = _safe_build(EntityRanker, default=None)
        self.clusterer = _safe_build(EntityClusterer, default=None)
        self.final_filter = _safe_build(EntityFinalFilter, default=None)

        self.description_extractor = _safe_build(DescriptionExtractor, default=None)
        self.property_enricher = _safe_build(PropertyEnricher, default=None)
        self.wikidata_linker = _safe_build(WikidataLinker, default=None)
        self.geo_resolver = _safe_build(
            HybridGeoResolver,
            default=None,
            default_city=kwargs.get("geo_default_city", "Pamplona"),
        )
        self.tourism_property_extractor = _safe_build(TourismPropertyExtractor, default=None)
        self.dom_image_resolver = _safe_build(DOMImageResolver, default=None)
        self.image_enricher = _safe_build(ImageEnricher, default=None)

        self.llm_supervisor = _safe_build(
            LLMSupervisor,
            self.ontology_catalog,
            use_fewshots=self.use_fewshots,
            fewshots=kwargs.get("fewshots") or [],
            default=None,
        )
        self.poi_discovery = _safe_build(POIDiscovery, default=None)
        self.event_detector = _safe_build(EventDetector, default=None)
        self.semantic_type_guesser = _safe_build(SemanticTypeGuesser, default=None)
        self.relation_extractor = _safe_build(RelationExtractor, default=None)
        self.entity_scorer = _safe_build(EntityScorer, default=None)
        self.entity_graph_builder = _safe_build(EntityGraphBuilder, default=None)
        self.page_entity_resolver = _safe_build(PageEntityResolver, default=None)
        self.block_quality_scorer = _safe_build(BlockQualityScorer, default=None)
        self.entity_evidence_builder = _safe_build(EntityEvidenceBuilder, default=None)
        self.ontology_reasoner = _safe_build(OntologyReasoner, default=None)

        self.global_memory = _safe_build(GlobalEntityMemory, default=None)
        self.graph_builder = _safe_build(EntityGraphBuilder, default=None)

        self.enable_entity_postprocess = True
        self.enable_entity_dedupe = True

        self.portal_category_terms = {
            "turismo", "gastronomia", "gastronomía", "cultura", "historia",
            "eventos", "lugares", "museos", "hoteles", "restaurantes",
            "alojarse", "comer", "que ver", "qué ver", "que hacer", "qué hacer",
            "viaje", "planifica", "salud", "familias", "mapas",
            "excursiones", "visitas", "monumentos", "rutas", "agenda",
            "noticias", "programa", "experiencias", "planes", "descubre",
            "disfruta", "ven", "profesionales",
        }

        self.ui_noise_patterns = {
            "ver más", "ver mas", "leer más", "leer mas", "mostrar más", "mostrar mas",
            "abrir", "google maps", "copiar dirección", "copiar direccion",
            "compartir", "contacto", "sitio web", "llamar", "cómo llegar",
            "reserva tu actividad", "ir al contenido", "pago recomendado",
        }

        self.navigation_patterns = {
            "inicio", "home", "siguiente", "anterior", "breadcrumb",
            "menu", "menú", "volver", "subir", "más info", "mas info",
        }

        self.weak_leading_patterns = [
            r"^(también|tambien)\b",
            r"^(comenzaremos|comenzara|comenzará)\b",
            r"^(además|ademas)\b",
            r"^(por supuesto)\b",
            r"^(actividad)\b",
            r"^(visita guiada)\b",
            r"^(festival)\b(?=.*\b20\d{2}\b)",  # deja caer en normalización si es título ruidoso
        ]

        self.trailing_noise_patterns = [
            r"\b(ver|más|mas|también|tambien|comenzaremos|pago recomendado)$",
            r"\b(monumento|monumentos|museo|museos|iglesia|iglesias|lugares|interés|interes)$",
            r"\b(preguntas|informacion|información|reserva|reservar|contacto|como llegar|cómo llegar|horarios|tarifas|precios)$",
        ]

        if self.debug:
            print("[INIT] TourismPipeline initialized")
            print(f"  - ontology_path: {ontology_path}")
            print(f"  - use_fewshots: {use_fewshots}")
            print(f"  - benchmark_mode: {benchmark_mode}")
            print(f"  - valid_classes: {len(self.valid_classes)}")
            print(f"  - ontology_matcher: {type(self.ontology_matcher).__name__ if self.ontology_matcher else None}")
            print(f"  - semantic_matcher: {type(self.semantic_matcher).__name__ if self.semantic_matcher else None}")
            print(f"  - ranker: {type(self.ranker).__name__ if self.ranker else None}")
            print(f"  - final_filter: {type(self.final_filter).__name__ if self.final_filter else None}")

        self.reset_runtime_state()

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

    def _normalized_for_match(self, text):
        t = self._scalar_text(text).lower().strip()
        t = re.sub(r"[^\wáéíóúñü\s\-]", " ", t, flags=re.IGNORECASE)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _canonical_key(self, text: str) -> str:
        t = self._normalized_for_match(text)
        t = re.sub(r"\b(ver|más|mas|si|no|también|tambien|comenzaremos|actividad)\b", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _normalize_candidate_type_name(self, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            return ""
        if value in self.valid_classes:
            return value

        value_slug = re.sub(r"[^a-z0-9]+", "", value.lower())
        if not value_slug:
            return ""

        for candidate in self.valid_classes:
            candidate_slug = re.sub(r"[^a-z0-9]+", "", candidate.lower())
            if value_slug == candidate_slug:
                return candidate
        return value

    def _tokenize_name(self, text: str) -> List[str]:
        return [t for t in re.split(r"[^\wáéíóúñü]+", self._normalized_for_match(text)) if t]

    def _extract_url_path_tokens(self, url: str) -> List[str]:
        try:
            path = urlparse(url or "").path.lower()
        except Exception:
            return []
        return [t for t in re.split(r"[^\wáéíóúñü]+", path) if t]

    def _looks_like_person_name(self, text: str) -> bool:
        """
        Señal débil. NO implica clase final persona.
        Solo reduce confianza cuando parece nombre propio aislado sin contexto turístico.
        """
        text = self._scalar_text(text).strip()
        if not text:
            return False

        tokens = [t for t in re.split(r"\s+", text) if t]
        if len(tokens) < 2 or len(tokens) > 4:
            return False

        if any(tok.lower() in {"de", "del", "la", "el", "los", "las"} for tok in tokens):
            return False

        cap_tokens = sum(1 for tok in tokens if tok[:1].isupper())
        if cap_tokens < max(2, len(tokens) - 1):
            return False

        monument_markers = {
            "catedral", "iglesia", "capilla", "museo", "palacio", "plaza",
            "parque", "monumento", "estatua", "escultura", "ayuntamiento",
        }
        lowered = self._normalized_for_match(text)
        if any(m in lowered for m in monument_markers):
            return False

        return True

    def _clean_candidate_name(self, name: str) -> str:
        text = self._scalar_text(name)
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            return ""

        for pat in self.weak_leading_patterns:
            text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()

        for pat in self.trailing_noise_patterns:
            text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()

        text = re.sub(
            r"\b(PAGO RECOMENDADO|Ver|Más|Mas|También|Tambien|Comenzaremos|Saber|Ir|Qué|Que|Tradiciones|Recomendaciones|Descubrir|Descubre)\b$",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        text = re.sub(
            r"^\s*Ayuntamiento\s+de\s+Pamplona\s+",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        for prefix in (
            "Todos los lugares ",
            "Todas las noticias ",
            "Categorias ",
            "Categorías ",
            "Que ver ",
            "Qué ver ",
            "Que hacer ",
            "Qué hacer ",
            "Donde comer ",
            "Dónde comer ",
            "Pensiones y hostales ",
            "Albergues ",
            "Campings ",
            "Excursiones desde Pamplona ",
            "Paseos y rutas ",
            "Hoteles ",
            "Restaurantes ",
            "Mercados ",
        ):
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()

        text = re.sub(r"\s+", " ", text).strip(" -|,;:")

        return text

    def _is_narrative_side_entity(
        self,
        entity_name: str,
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ) -> bool:
        name = self._normalized_for_match(entity_name)
        if not name:
            return False

        if self._is_primary_page_candidate_name(entity_name, page_signals=page_signals, url=url):
            return False

        url_low = self._normalized_for_match(url or page_signals.get("url") or "")
        route_like_page = any(token in url_low for token in ("ruta", "route", "hemingway", "paseos-y-rutas"))
        detail_like_page = self._is_detail_priority_page(page_signals=page_signals, url=url)

        if not (route_like_page or detail_like_page):
            return False

        narrative_markers = {
            "narra",
            "cerca",
            "adentrate",
            "adéntrate",
            "descubre",
            "historia",
            "biografia",
            "biografía",
            "guerra",
            "school",
        }
        person_like_markers = {
            "hemingway",
            "bacall",
            "barnes",
            "richardson",
            "jake",
            "elizabeth",
            "clarence",
            "mary",
            "ventura rodriguez",
            "ventura rodríguez",
            "johan lome",
        }

        if any(marker in name for marker in narrative_markers):
            return True

        if route_like_page and any(marker in name for marker in person_like_markers):
            return True

        if detail_like_page and len(name.split()) >= 3 and any(marker in name for marker in person_like_markers):
            return True

        return False

    def _is_phrase_fragment(self, entity_name: str) -> bool:
        key = self._canonical_key(entity_name)
        if not key:
            return True

        tokens = key.split()
        if len(tokens) >= 4:
            verbal_markers = {
                "es", "son", "fue", "fueron", "ser", "puede", "pueden", "comenzaremos",
                "combina", "data", "tienen", "ocurre", "permite", "ofrece", "ofrecen",
                "hacen", "hacer", "disfruta", "disfrutar", "vivir", "piensa", "piensan",
            }
            if any(tok in verbal_markers for tok in tokens):
                return True

        if re.search(r"\b(comenzaremos|también|tambien|además|ademas|por supuesto|quién fue|cuando|cuándo)\b", key):
            return True

        return False

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

            raw_name = (
                item.get("name")
                or item.get("entity_name")
                or item.get("entity")
                or item.get("label")
                or ""
            )
            clean_name = self._clean_candidate_name(raw_name)
            if clean_name:
                item["name"] = clean_name
                item["entity_name"] = clean_name
                item["label"] = clean_name
                item["entity"] = clean_name

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

    def _coerce_entities_to_dicts(self, entities: List[Any], url: str = "") -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []

        for item in entities or []:
            if item is None:
                continue

            if isinstance(item, dict):
                name = (
                    item.get("name")
                    or item.get("entity_name")
                    or item.get("entity")
                    or item.get("label")
                    or ""
                )
                if str(name).strip():
                    out.append(item)
                continue

            if isinstance(item, str):
                name = item.strip()
                if not name:
                    continue
                out.append({
                    "name": name,
                    "entity_name": name,
                    "label": name,
                    "type": "Unknown",
                    "class": "Unknown",
                    "sourceUrl": url or "",
                    "url": url or "",
                    "score": 0.5,
                })
                continue

            try:
                name = str(item).strip()
            except Exception:
                name = ""

            if name:
                out.append({
                    "name": name,
                    "entity_name": name,
                    "label": name,
                    "type": "Unknown",
                    "class": "Unknown",
                    "sourceUrl": url or "",
                    "url": url or "",
                    "score": 0.5,
                })

        return out

    def _is_forbidden_type(self, value: str) -> bool:
        short = str(value or "").split("#")[-1].split("/")[-1].strip()
        return short.lower() in {"", "thing", "unknown", "entity", "item", "location", "place", "person"}

    def _promote_semantic_type(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        promoted = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)
            semantic_type = str(item.get("semantic_type") or "").strip()

            if semantic_type:
                short_type = semantic_type.split("#")[-1].split("/")[-1].strip()

                if short_type.lower() == "concept":
                    short_type = "ConceptScheme"

                if short_type and not self._is_forbidden_type(short_type):
                    item["class"] = short_type
                    item["type"] = short_type
                elif short_type:
                    item["semantic_type"] = ""
                    item["semantic_type_rejected"] = short_type

            promoted.append(item)

        return promoted

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

    def _page_capture_profile(
        self,
        listing_like_page: bool = False,
        strict_listing_page: bool = False,
        detail_priority_page: bool = False,
    ) -> Dict[str, Any]:
        if strict_listing_page:
            return {
                "name": "strict_listing",
                "supplement_limit": 16,
                "evidence_rescue_score": 2.2,
                "quality_review_ok": True,
            }
        if listing_like_page:
            return {
                "name": "listing",
                "supplement_limit": 12,
                "evidence_rescue_score": 2.6,
                "quality_review_ok": True,
            }
        if detail_priority_page:
            return {
                "name": "detail_priority",
                "supplement_limit": 6,
                "evidence_rescue_score": 2.2,
                "quality_review_ok": True,
            }
        return {
            "name": "detail",
            "supplement_limit": 5,
            "evidence_rescue_score": 3.4,
            "quality_review_ok": False,
        }

    def _classify_page_intent(
        self,
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
    ) -> str:
        page_signals = page_signals or {}
        url_low = str(url or "").strip().lower()
        title = self._canonical_key(page_signals.get("title") or "")
        h1 = self._canonical_key(page_signals.get("h1") or "")
        breadcrumb = self._canonical_key(page_signals.get("breadcrumb") or "")
        slug = self._canonical_key(page_signals.get("slug") or "")
        text = self._canonical_key(page_text[:2000])
        combined = " | ".join(
            x for x in [title, h1, breadcrumb, slug, text, self._canonical_key(url)] if x
        )

        legal_markers = {
            "aviso legal",
            "politica de privacidad",
            "politica de cookies",
            "declaracion de accesibilidad",
            "declaracion accesibilidad",
            "privacy policy",
            "cookie policy",
            "legal notice",
        }
        technical_markers = {
            "elementor_library",
            "wp-json",
            "feed",
            "preview=true",
            "replytocom",
        }
        institutional_markers = {
            "area profesional",
            "estrategias y planes",
            "estudios e informes",
            "licitaciones",
            "plan de sostenibilidad",
            "pstd",
            "sf365",
        }
        programmatic_markers = {
            "plan",
            "estrategia",
            "estrategias",
            "informe",
            "informes",
            "licitacion",
            "licitaciones",
            "sostenibilidad",
            "promocion",
            "promociones",
            "marketing",
        }

        if any(marker in combined for marker in legal_markers):
            return "legal"

        if any(fragment in url_low for fragment in ("/aviso-legal", "privacidad", "cookies", "accesibilidad")):
            return "legal"

        if any(marker in combined for marker in technical_markers):
            return "technical"

        if any(fragment in url_low for fragment in ("elementor_library=", "wp-json", "/feed", "preview=true", "replytocom")):
            return "technical"

        if any(marker in combined for marker in institutional_markers):
            if any(marker in combined for marker in programmatic_markers):
                return "programmatic"
            return "institutional"

        if "/lugar/" in url_low or "/en/lugar/" in url_low:
            return "detail"

        if self._is_strict_listing_page(page_signals=page_signals, page_text=page_text, url=url):
            return "listing"

        if self._is_listing_like_page(page_signals=page_signals, page_text=page_text, url=url):
            return "listing"

        return "detail"

    def _should_ignore_page(self, page_signals: Optional[Dict[str, Any]] = None, url: str = "") -> bool:
        page_signals = page_signals or {}
        intent = str(page_signals.get("pageIntent") or "").strip().lower()
        if intent in {"legal", "technical"}:
            return True

        url_low = str(url or "").strip().lower()
        ignored_url_fragments = (
            "elementor_library=",
            "/aviso-legal",
            "privacidad",
            "cookies",
            "accesibilidad",
            "/feed/",
            "/feed",
            "wp-json",
        )
        return any(fragment in url_low for fragment in ignored_url_fragments)

    def _is_detail_priority_page(self, page_signals: Optional[Dict[str, Any]] = None, url: str = "") -> bool:
        page_signals = page_signals or {}
        url_low = str(url or page_signals.get("url") or "").strip().lower()
        return "/lugar/" in url_low or "/en/lugar/" in url_low

    def _is_primary_page_candidate_name(
        self,
        name: str,
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ) -> bool:
        page_signals = page_signals or {}
        norm_name = self._normalized_for_match(name)
        if not norm_name:
            return False

        title = self._normalized_for_match(page_signals.get("title") or "")
        h1 = self._normalized_for_match(page_signals.get("h1") or "")
        slug = self._normalized_for_match(page_signals.get("slug") or self._extract_url_slug(url))

        return any(
            (
                norm_name == candidate
                or (candidate and norm_name in candidate)
                or (candidate and candidate in norm_name)
            )
            for candidate in (title, h1, slug)
            if candidate
        )

    def _is_route_like_page(self, page_signals: Optional[Dict[str, Any]] = None, url: str = "") -> bool:
        page_signals = page_signals or {}
        merged = " ".join(
            str(x or "")
            for x in [
                url or page_signals.get("url") or "",
                page_signals.get("title") or "",
                page_signals.get("h1") or "",
                page_signals.get("breadcrumb") or "",
                page_signals.get("slug") or "",
            ]
        )
        merged = self._normalized_for_match(merged)
        route_markers = ("ruta", "route", "camino", "itinerario", "sendero", "via verde")
        return any(marker in merged for marker in route_markers)

    def _is_structure_child_candidate(self, entity: Dict[str, Any]) -> bool:
        entity_type = self._normalized_for_match(entity.get("class") or entity.get("type") or "")
        if not entity_type or entity_type in {"unknown", "thing", "concept", "conceptscheme", "person", "event"}:
            return False
        if entity_type == "route":
            return False
        name = str(entity.get("name") or entity.get("entity_name") or entity.get("label") or "").strip()
        return bool(name)

    def _build_entity_stable_id(self, entity: Dict[str, Any], page_url: str, used_ids: set) -> str:
        page_slug = self._extract_url_slug(page_url) or "page"
        name = (
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or "entity"
        )
        base = f"{page_slug}__{self._canonical_key(name).replace(' ', '_') or 'entity'}"
        entity_id = base
        suffix = 2
        while entity_id in used_ids:
            entity_id = f"{base}_{suffix}"
            suffix += 1
        used_ids.add(entity_id)
        return entity_id

    def _pick_structural_primary_entity(
        self,
        entities: List[Dict[str, Any]],
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ) -> Optional[Dict[str, Any]]:
        if not entities:
            return None

        page_signals = page_signals or {}
        route_like_page = self._is_route_like_page(page_signals=page_signals, url=url)

        def candidate_score(item: Dict[str, Any]) -> tuple:
            name = str(item.get("name") or item.get("entity_name") or item.get("label") or "").strip()
            entity_type = self._normalized_for_match(item.get("class") or item.get("type") or "")
            score = float(item.get("score") or 0.0)
            return (
                1 if self._is_primary_page_candidate_name(name, page_signals=page_signals, url=url) else 0,
                1 if route_like_page and entity_type == "route" else 0,
                1 if item.get("_synthetic_primary_candidate") or item.get("_detail_priority_seed") else 0,
                score,
                len(name),
            )

        ordered = sorted((item for item in entities if isinstance(item, dict)), key=candidate_score, reverse=True)
        best = ordered[0] if ordered else None
        if not best:
            return None

        best_name = str(best.get("name") or best.get("entity_name") or best.get("label") or "").strip()
        if not best_name:
            return None

        if route_like_page:
            best_type = self._normalized_for_match(best.get("class") or best.get("type") or "")
            if best_type == "route" or self._looks_like_route_entity_name(best_name):
                return best
            return None

        if self._is_primary_page_candidate_name(best_name, page_signals=page_signals, url=url):
            return best
        return None

    def _annotate_page_structure(
        self,
        entities: List[Dict[str, Any]],
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ) -> List[Dict[str, Any]]:
        annotated = [dict(entity) for entity in entities if isinstance(entity, dict)]
        if not annotated:
            return annotated

        page_signals = page_signals or {}
        page_url = url or page_signals.get("url") or ""
        used_ids = set()
        primary = self._pick_structural_primary_entity(annotated, page_signals=page_signals, url=url)
        primary_key = self._canonical_key(
            primary.get("name") or primary.get("entity_name") or primary.get("label") or ""
        ) if primary else ""

        route_like_page = self._is_route_like_page(page_signals=page_signals, url=url)
        child_count = 0

        for entity in annotated:
            entity["entityId"] = self._build_entity_stable_id(entity, page_url, used_ids)

        if len(annotated) == 1:
            structure = "single"
        else:
            structure = "flat"

        if primary_key and route_like_page:
            for entity in annotated:
                name_key = self._canonical_key(entity.get("name") or entity.get("entity_name") or entity.get("label") or "")
                if name_key and name_key != primary_key and self._is_structure_child_candidate(entity):
                    child_count += 1
            if child_count >= 1:
                structure = "hierarchical"

        primary_id = ""
        if primary:
            primary_id = str(primary.get("entityId") or "")

        for entity in annotated:
            name_key = self._canonical_key(entity.get("name") or entity.get("entity_name") or entity.get("label") or "")
            entity["pageStructure"] = structure
            entity["parentEntityId"] = None
            entity["relationshipType"] = None

            if structure == "single":
                entity["pageRole"] = "primary"
                continue

            if structure == "hierarchical" and primary_id:
                if name_key == primary_key:
                    entity["pageRole"] = "primary"
                elif self._is_structure_child_candidate(entity):
                    entity["pageRole"] = "child"
                    entity["parentEntityId"] = primary_id
                    entity["relationshipType"] = "includesStop"
                else:
                    entity["pageRole"] = "secondary"
                continue

            if primary_key and name_key == primary_key:
                entity["pageRole"] = "primary"
            else:
                entity["pageRole"] = "standalone"

        return annotated

    def _align_entities_with_page_subject(
        self,
        entities: List[Dict[str, Any]],
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ) -> List[Dict[str, Any]]:
        aligned = [dict(entity) for entity in entities if isinstance(entity, dict)]
        if not aligned:
            return aligned

        page_signals = page_signals or {}
        subject_name = self._clean_candidate_name(page_signals.get("pageSubject") or "")
        subject_norm = self._normalized_for_match(subject_name)
        subject_class = str(page_signals.get("pageSubjectClass") or "").strip()
        subject_confidence = float(page_signals.get("pageSubjectConfidence") or 0.0)
        if not subject_name or subject_confidence < 0.8:
            return aligned

        transport_like_page = self._is_transport_like_page(page_signals=page_signals, url=url)
        for entity in aligned:
            name = self._clean_candidate_name(
                entity.get("name")
                or entity.get("entity_name")
                or entity.get("entity")
                or entity.get("label")
                or ""
            )
            name_norm = self._normalized_for_match(name)
            entity_class = str(entity.get("class") or entity.get("type") or "").strip()
            page_role = str(entity.get("pageRole") or "").strip().lower()
            if page_role and page_role != "primary":
                continue

            if subject_class and entity_class and subject_class != entity_class:
                continue

            generic_transport_name = name_norm in {
                "estacion de autobuses",
                "estación de autobuses",
                "estacion de tren",
                "estación de tren",
                "aeropuerto",
                "puerto",
            }
            weak_partial = bool(name_norm and name_norm in subject_norm and len(name_norm.split()) <= 3)
            mixed_hybrid = transport_like_page and bool(name_norm) and any(
                marker in name_norm for marker in ("estacion", "estación", "aeropuerto", "puerto")
            ) and name_norm != subject_norm and subject_norm not in name_norm and name_norm not in subject_norm

            if generic_transport_name or weak_partial or mixed_hybrid:
                entity["name"] = subject_name
                entity["entity_name"] = subject_name
                entity["label"] = subject_name
                entity["entity"] = subject_name
                entity["_page_subject_aligned"] = True

        return aligned

    def _is_detail_secondary_label(
        self,
        entity_name: str,
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ) -> bool:
        if not self._is_detail_priority_page(page_signals=page_signals, url=url):
            return False

        if self._is_primary_page_candidate_name(entity_name, page_signals=page_signals, url=url):
            return False

        name = self._normalized_for_match(entity_name)
        if not name:
            return False

        generic_labels = {
            "visitas para grupos",
            "visitas en familia",
            "actividades deportivas",
            "localizacion",
            "ubicacion",
            "como llegar",
            "informacion practica",
            "informacion adicional",
            "horarios",
            "precios",
            "tarifas",
            "reservas",
            "reserva",
            "contacto",
            "group visits",
            "family visits",
            "sports activities",
            "location",
            "how to get there",
            "opening hours",
            "prices",
            "rates",
            "booking",
            "bookings",
            "contact",
        }
        if name in generic_labels:
            return True

        weak_patterns = (
            "visitas ",
            "visita ",
            "grupos",
            "familia",
            "how to ",
            "como ",
            "opening ",
            "booking",
            "reserv",
            "horario",
            "precio",
            "tarifa",
            "contact",
            "localizacion",
            "ubicacion",
            "location ",
        )
        return any(term in name for term in weak_patterns)

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

        if self._is_phrase_fragment(key):
            return True

        if re.search(r"\b(ver|más|mas|si|también|tambien|comenzaremos)\b", key):
            return True

        generic_terms = {
            "hotel", "hoteles", "hostel", "hostales", "albergue", "albergues",
            "museo", "museos", "mercado", "mercados", "festival", "festivales",
            "excursiones", "visitas", "lugares", "monumentos", "catedral",
            "catedrales", "plaza", "plazas", "parque", "parques", "turismo",
            "gastronomia", "gastronomía", "mapas", "familias", "agenda",
            "programa", "noticias", "actividad", "experiencias",
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
        page_signals = page_signals or {}

        if not key:
            return 10.0

        words = key.split()

        if len(words) == 1:
            penalty += 2.0

        if self._looks_like_ui_or_category_name(key):
            penalty += 8.0

        if self._looks_like_bad_compound_entity(key):
            penalty += 8.0

        if self._looks_like_person_name(entity_name):
            penalty += 1.25  # señal débil, no veto

        if self._looks_like_technical_noise_entity(entity_name):
            penalty += 6.0

        primary_candidates = self._extract_primary_page_entity_candidates(
            title=page_signals.get("title") or "",
            h1=page_signals.get("h1") or "",
        )
        if self._is_subordinate_event_label(entity_name, primary_candidates=primary_candidates):
            penalty += 5.0
        if self._is_detail_secondary_label(entity_name, page_signals=page_signals, url=url):
            penalty += 8.0
        if self._is_narrative_side_entity(entity_name, page_signals=page_signals, url=url):
            penalty += 8.0

        if re.search(r"\b(ver|más|mas|si|también|tambien|comenzaremos)\b", key):
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
            "glorieta", "conjunto escultorico",
            "homenaje a", "dedicado a", "obra de", "escultor",
            "figura de bronce", "escultorico", "fachada",
            "claustro", "retablo", "nave central",
        ]

        event_terms = [
            "bienal", "festival", "feria", "semana santa",
            "procesion", "congreso", "ciclo",
        ]

        route_terms = [
            "ruta", "camino", "eurovelo", "cicloturismo",
            "via verde", "sendero", "itinerario",
        ]

        sports_terms = [
            "pump track", "skate park", "skatepark", "skate",
            "instalacion deportiva", "deporte sobre ruedas",
            "patin", "patinaje", "rocodromo", "rocopolis",
            "circuito deportivo",
        ]

        heritage_terms = [
            "archivo", "archivo real", "archivo general",
            "edificio historico", "patrimonio historico",
            "patrimonio cultural", "claustro", "fachada",
            "retablo", "nave central", "capitel",
        ]

        place_prefix_map = {
            "plaza ": "Square",
            "parque ": "UrbanPark",
            "jardin ": "Garden",
            "mercado ": "Market",
            "barrio ": "Neighborhood",
            "puerta ": "Gate",
            "glorieta ": "Roundabout",
        }

        monument_prefixes = [
            "basilica ", "catedral ", "iglesia ", "capilla ",
            "palacio ", "alcazar ", "torre ", "puente ",
            "monasterio ", "convento ", "ayuntamiento ",
        ]

        if any(term in name for term in event_terms):
            return "Event"

        strong_route_name_terms = [
            "ruta ", "camino ", "camino de ", "eurovelo", "cicloturismo",
            "via verde", "sendero", "itinerario",
        ]

        if any(term in name for term in strong_route_name_terms):
            return "Route"

        if any(term in name for term in sports_terms) or any(term in context for term in sports_terms):
            return "SportsCenter"

        for prefix, guessed in place_prefix_map.items():
            if name.startswith(prefix):
                return guessed

        if any(name.startswith(prefix) for prefix in monument_prefixes):
            if name.startswith("ayuntamiento "):
                return "TownHall"
            if name.startswith("catedral "):
                return "Cathedral"
            if name.startswith("iglesia "):
                return "Church"
            if name.startswith("capilla "):
                return "Chapel"
            if name.startswith("basilica "):
                return "Basilica"
            if name.startswith("palacio "):
                return "Palace"
            return "Monument"

        if "camino de santiago" in name:
            return "Route"

        if "archivo" in name:
            return "HistoricalOrCulturalResource"

        if any(term in context for term in monument_context_terms):
            return "Monument"

        if any(term in context for term in heritage_terms):
            return "HistoricalOrCulturalResource"

        if any(k in name for k in ["tradicion", "cultura", "patrimonio inmaterial"]):
            return "ConceptScheme"

        return current_type or ""

    def _normalize_programmatic_type(
        self,
        name: str,
        current_type: str,
        page_signals: Optional[Dict[str, Any]] = None,
    ) -> str:
        page_signals = page_signals or {}
        if str(page_signals.get("pageIntent") or "").strip().lower() != "programmatic":
            return current_type or ""

        current = str(current_type or "").strip()
        current_low = current.lower()
        name_low = self._normalized_for_match(name)

        suspicious_physical = {
            "garden",
            "square",
            "cathedral",
            "church",
            "chapel",
            "palace",
            "castle",
            "monument",
            "bridge",
            "wall",
            "museum",
        }

        if any(term in name_low for term in ("congreso", "simposio", "jornadas", "convencion", "convención", "asamblea", "festival")):
            return "Event"

        if any(term in name_low for term in ("plan", "estrategia", "estudio", "informe", "analisis", "análisis", "licitacion", "licitación", "gobernanza", "marketing", "movilidad", "eficiencia", "rehabilitacion", "rehabilitación")):
            return "TourismService" if "TourismService" in self.valid_classes else "PublicService"

        if current_low in suspicious_physical:
            return "TourismService" if "TourismService" in self.valid_classes else "PublicService"

        return current

    def _normalize_unknown_family_type(
        self,
        name: str,
        current_type: str,
        page_signals: Optional[Dict[str, Any]] = None,
    ) -> str:
        current = str(current_type or "").strip()
        page_signals = page_signals or {}
        name_low = self._normalized_for_match(name)
        url_low = self._normalized_for_match(page_signals.get("url") or "")

        if current and current.lower() not in {"unknown", ""}:
            return current

        if any(term in name_low for term in ("congreso", "simposio", "jornadas", "convencion", "convención", "asamblea", "startup day")):
            return "Event"

        gastronomic_product_terms = (
            "pimientos del piquillo",
            "queso roncal",
            "sidra navarra",
            "torta de txantxigorri",
            "chistorra",
            "cuajada",
            "goxua",
            "pantxineta",
            "patxaran",
            "ajoarriero",
            "fritos",
            "pochas",
            "espárragos",
            "esparragos",
        )
        if any(term in name_low for term in gastronomic_product_terms):
            return "FoodEstablishment" if "FoodEstablishment" in self.valid_classes else "HistoricalOrCulturalResource"

        if any(term in name_low for term in ("consignas", "consigna", "locker", "lockers", "guarda equipajes")):
            return "PublicService" if "PublicService" in self.valid_classes else current

        if any(term in name_low for term in ("club de producto", "indicaciones geograficas protegidas", "indicaciones geográficas protegidas", "reyno gourmet")):
            return "HistoricalOrCulturalResource"

        if ("/eventos-del-sector" in url_low) and any(term in name_low for term in ("congreso", "simposio", "jornadas", "convencion", "convención")):
            return "Event"

        return current

    def _ensure_entity_type(
        self,
        entities,
        page_text: str = "",
        page_signals=None,
        expected_type: str = None,
    ):
        fixed = []

        weak_types = {"", "thing", "unknown", "entity", "item", "location", "place", "person"}
        forbidden_final_types = {"thing", "location", "person"}

        route_like_class = choose_route_like_class(self.valid_classes)
        event_like_class = choose_event_class(self.valid_classes)

        def normalize_candidate_type(value: str) -> str:
            value = str(value or "").strip()
            if not value:
                return ""

            short = value.split("#")[-1].split("/")[-1].strip()
            if not short:
                return ""

            aliases = {
                "organisation": "TourismOrganisation",
                "organization": "TourismOrganisation",
                "medicalclinic": "PublicService",
                "clinic": "PublicService",
                "healthcareorganization": "PublicService",
                "healthcarefacility": "PublicService",
                "eventorganisationcompany": "EventOrganisationCompany",
                "route": route_like_class if route_like_class != "Unknown" else "Route",
                "ruta": route_like_class if route_like_class != "Unknown" else "Route",
                "guidedtour": "DestinationExperience",
                "excursion": "DestinationExperience",
                "activity": "DestinationExperience",
                "concept": "ConceptScheme",
                "place": "",
                "market": "Market",
                "square": "Square",
                "garden": "Garden",
                "urbanpark": "UrbanPark",
                "neighborhood": "Neighborhood",
                "gate": "Gate",
                "roundabout": "Roundabout",
                "person": "",
            }

            normalized = aliases.get(short.lower(), short)
            if normalized.lower() in weak_types:
                return ""
            return normalized

        def build_context(item: dict) -> str:
            return " ".join([
                strip_sitewide_footer_text(item.get("shortDescription") or item.get("short_description") or ""),
                strip_sitewide_footer_text(item.get("longDescription") or item.get("long_description") or ""),
                strip_sitewide_footer_text(item.get("description") or ""),
                strip_sitewide_footer_text(page_text or ""),
            ])

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)

            raw_name = (
                item.get("name")
                or item.get("entity_name")
                or item.get("entity")
                or item.get("label")
                or ""
            )
            name = self._clean_candidate_name(raw_name)
            item["name"] = name
            item["entity_name"] = name
            item["label"] = name
            item["entity"] = name

            current_class = str(item.get("class") or "").strip()
            current_type = str(item.get("type") or "").strip()
            semantic_type = str(item.get("semantic_type") or "").strip()

            props = item.get("properties") if isinstance(item.get("properties"), dict) else {}
            prop_type = str(props.get("type") or "").strip()

            normalized_class = normalize_candidate_type(current_class)
            normalized_type = normalize_candidate_type(current_type)
            normalized_semantic = normalize_candidate_type(semantic_type)
            normalized_prop_type = normalize_candidate_type(prop_type)

            canonical_type = (
                normalized_class
                or normalized_type
                or normalized_semantic
                or normalized_prop_type
            )
            canonical_type = self._normalize_unknown_family_type(
                name=name,
                current_type=canonical_type,
                page_signals=page_signals or {},
            )

            name_norm = self._normalized_for_match(name)
            context_norm = self._normalized_for_match(build_context(item))

            if "san fermin" in name_norm or "san fermín" in name_norm:
                if event_like_class != "Unknown":
                    item["class"] = event_like_class
                    item["type"] = event_like_class
                    fixed.append(item)
                    continue

            if "camino de santiago" in name_norm:
                if route_like_class != "Unknown":
                    item["class"] = route_like_class
                    item["type"] = route_like_class
                    fixed.append(item)
                    continue

            if name_norm.startswith("catedral ") and "Cathedral" in self.valid_classes:
                item["class"] = "Cathedral"
                item["type"] = "Cathedral"
                fixed.append(item)
                continue

            if (
                re.search(r"^(ayuntamiento|casa consistorial)\b", name_norm)
                and not re.search(
                    r"\b(casco antiguo|festival|pump track|frente ciudadela|estrellas michelin|queso|alojamientos|verde|reserva|preguntas|mercados|agroturismos|cordero|menestra|patxaran|actas|pimientos|ajoarriero|trucha|pochas|esparragos|cuajada|chistorra|goxua|pantxineta|fritos|planes|cultura)\b",
                    name_norm,
                )
                and "TownHall" in self.valid_classes
            ):
                item["class"] = "TownHall"
                item["type"] = "TownHall"
                fixed.append(item)
                continue

            if canonical_type and canonical_type.lower() not in weak_types and canonical_type.lower() not in forbidden_final_types:
                canonical_type = self._normalize_programmatic_type(
                    name=name,
                    current_type=canonical_type,
                    page_signals=page_signals or {},
                )
                item["class"] = canonical_type
                item["type"] = canonical_type
                fixed.append(item)
                continue

            if self.type_resolver is not None and hasattr(self.type_resolver, "resolve"):
                try:
                    resolved = self.type_resolver.resolve(
                        mention=name,
                        context=build_context(item),
                        block_text=item.get("source_text") or "",
                        page_signals=page_signals or {},
                        properties=item,
                        expected_type=expected_type,
                        ontology_candidates=item.get("ontology_candidates") or [],
                    )
                except Exception:
                    resolved = {}
            else:
                resolved = {}

            resolved_class = normalize_candidate_type(str((resolved or {}).get("class") or "Unknown").strip())
            item["type_resolution"] = resolved

            if not resolved_class or resolved_class.lower() in weak_types or resolved_class.lower() in forbidden_final_types:
                guessed = self._guess_type_from_name_and_context(
                    entity_name=name,
                    page_text=build_context(item),
                    current_type="",
                )
                guessed = self._normalize_programmatic_type(
                    name=name,
                    current_type=guessed,
                    page_signals=page_signals or {},
                )
                guessed = self._normalize_unknown_family_type(
                    name=name,
                    current_type=guessed,
                    page_signals=page_signals or {},
                )
                guessed = normalize_candidate_type(guessed)

                if guessed and guessed.lower() not in forbidden_final_types and guessed.lower() not in weak_types:
                    item["class"] = guessed
                    item["type"] = guessed
                else:
                    item["class"] = "Unknown"
                    item["type"] = "Unknown"
            else:
                item["class"] = resolved_class
                item["type"] = resolved_class

            if str(item.get("class") or "").strip() in {"Unknown", "Place", "Location", "HistoricalOrCulturalResource"}:
                upgraded = normalize_candidate_type(
                    self._guess_type_from_name_and_context(
                        entity_name=name,
                        page_text=build_context(item),
                        current_type=str(item.get("class") or ""),
                    )
                )
                if upgraded and upgraded.lower() not in forbidden_final_types and upgraded.lower() not in weak_types:
                    item["class"] = upgraded
                    item["type"] = upgraded

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

    def _clean_heading_candidate(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""

        value = re.sub(r"\s+", " ", value)
        for separator in (" | ", " - ", " – ", " — ", " » "):
            if separator in value:
                value = value.split(separator)[0].strip()

        low = self._normalized_for_match(value)
        for prefix in ("ir al contenido", "reserva tu actividad", "descubre pamplona", "planifica tu viaje"):
            if low.startswith(prefix + " "):
                value = value[len(prefix):].strip()
                low = self._normalized_for_match(value)

        return self._clean_candidate_name(value)

    def _clean_route_parent_name(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return ""

        value = re.sub(r"\s+", " ", value).strip()
        for separator in (" | ", " - "):
            if separator in value:
                value = value.split(separator)[0].strip()

        low = self._normalized_for_match(value)
        for prefix in ("ir al contenido", "reserva tu actividad", "descubre pamplona", "planifica tu viaje"):
            if low.startswith(prefix + " "):
                value = value[len(prefix):].strip()
                low = self._normalized_for_match(value)

        value = re.sub(r"\b(Distancia|Tiempo recomendado)\b.*$", "", value, flags=re.IGNORECASE).strip()
        value = re.sub(r"\s+", " ", value).strip(" -|,;:")
        return value

    def _extract_primary_page_entity_candidates(self, title: str = "", h1: str = "") -> List[str]:
        anchor_pattern = re.compile(
            r"\b(?:Festival|Mercado|Feria|Ruta|Camino|Museo|Catedral|Iglesia|Capilla|Castillo|"
            r"Palacio|Plaza|Ayuntamiento|Parque|Puente|Estacion|Oficina de Turismo)\b"
            r"(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9'’-]+){0,16}",
            flags=re.IGNORECASE,
        )
        candidates: List[str] = []
        seen = set()

        for raw in (h1, title):
            cleaned = self._clean_heading_candidate(raw)
            if not cleaned:
                continue

            direct = cleaned.strip(" ,.;:-|")
            if direct and len(direct.split()) <= 18:
                direct_key = self._canonical_key(direct)
                if (
                    direct_key
                    and direct_key not in seen
                    and not self._is_contextual_noise_entity(direct)
                    and not self._looks_like_ui_or_category_name(direct)
                ):
                    seen.add(direct_key)
                    candidates.append(direct)

            for match in anchor_pattern.findall(cleaned):
                candidate = self._clean_candidate_name(match)
                key = self._canonical_key(candidate)
                if not key or key in seen:
                    continue
                if self._is_contextual_noise_entity(candidate):
                    continue
                if self._looks_like_ui_or_category_name(candidate):
                    continue
                seen.add(key)
                candidates.append(candidate)

        return candidates

    def _is_transport_like_page(self, page_signals: Optional[Dict[str, Any]] = None, url: str = "") -> bool:
        page_signals = page_signals or {}
        merged = " ".join(
            str(x or "")
            for x in [
                url or page_signals.get("url") or "",
                page_signals.get("title") or "",
                page_signals.get("h1") or "",
                page_signals.get("breadcrumb") or "",
                page_signals.get("slug") or "",
            ]
        )
        merged = self._normalized_for_match(merged)
        markers = (
            "transporte",
            "estacion de tren",
            "estación de tren",
            "estacion de autobuses",
            "estación de autobuses",
            "aeropuerto",
            "puerto",
        )
        return any(marker in merged for marker in markers)

    def _page_subject_match_score(
        self,
        candidate: str,
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
    ) -> float:
        candidate_norm = self._normalized_for_match(candidate)
        if not candidate_norm:
            return 0.0

        page_signals = page_signals or {}
        title = self._normalized_for_match(page_signals.get("title") or "")
        h1 = self._normalized_for_match(page_signals.get("h1") or "")
        breadcrumb = self._normalized_for_match(page_signals.get("breadcrumb") or "")
        slug = self._normalized_for_match(page_signals.get("slug") or self._extract_url_slug(url))
        text = self._normalized_for_match((page_text or "")[:1800])

        score = 0.0
        if h1 and (candidate_norm == h1 or candidate_norm in h1 or h1 in candidate_norm):
            score += 4.0
        if title and (candidate_norm == title or candidate_norm in title or title in candidate_norm):
            score += 3.0
        if breadcrumb and (candidate_norm in breadcrumb or breadcrumb in candidate_norm):
            score += 1.0
        if slug and any(token in slug for token in self._tokenize_name(candidate_norm) if len(token) > 3):
            score += 1.5
        if text and candidate_norm in text:
            score += 1.5

        token_hits = sum(1 for token in self._tokenize_name(candidate_norm) if len(token) > 3 and token in text)
        score += min(2.0, token_hits * 0.4)
        return score

    def _detect_page_subject(
        self,
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
    ) -> Dict[str, Any]:
        page_signals = page_signals or {}
        candidates = self._extract_primary_page_entity_candidates(
            title=page_signals.get("title") or "",
            h1=page_signals.get("h1") or "",
        )

        if not candidates:
            return {
                "name": "",
                "class": "",
                "confidence": 0.0,
                "evidence": [],
            }

        scored = []
        for candidate in candidates:
            score = self._page_subject_match_score(
                candidate,
                page_signals=page_signals,
                page_text=page_text,
                url=url,
            )
            scored.append((score, candidate))

        transport_like_page = self._is_transport_like_page(page_signals=page_signals, url=url)
        if transport_like_page:
            direct_h1 = self._clean_heading_candidate(page_signals.get("h1") or "")
            direct_title = self._clean_heading_candidate(page_signals.get("title") or "")
            boosted = []
            for score, candidate in scored:
                extra = 0.0
                candidate_norm = self._normalized_for_match(candidate)
                if direct_h1 and candidate_norm == self._normalized_for_match(direct_h1):
                    extra += 3.0
                if direct_title and candidate_norm == self._normalized_for_match(direct_title):
                    extra += 2.0
                boosted.append((score + extra, candidate))
            scored = boosted

        scored.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
        best_score, best_candidate = scored[0]
        if best_score <= 0:
            return {
                "name": "",
                "class": "",
                "confidence": 0.0,
                "evidence": [],
            }

        guessed_class = self._normalize_candidate_type_name(
            self._guess_type_from_name_and_context(
                entity_name=best_candidate,
                page_text=" ".join(
                    x for x in [
                        page_signals.get("h1") or "",
                        page_signals.get("title") or "",
                        page_signals.get("breadcrumb") or "",
                        page_text[:1200] if page_text else "",
                    ] if x
                ),
                current_type="",
            )
        )
        guessed_class = self._normalize_unknown_family_type(
            name=best_candidate,
            current_type=guessed_class,
            page_signals=page_signals,
        )
        guessed_class = self._normalize_candidate_type_name(guessed_class)

        confidence = min(1.0, round(best_score / 8.0, 3))
        evidence = [candidate for _, candidate in scored[:3]]
        return {
            "name": best_candidate,
            "class": guessed_class or "",
            "confidence": confidence,
            "evidence": evidence,
        }

    def _seed_detail_primary_candidates(
        self,
        entities,
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ):
        page_signals = page_signals or {}
        title = page_signals.get("title") or ""
        h1 = page_signals.get("h1") or ""
        primary_candidates = self._extract_primary_page_entity_candidates(title=title, h1=h1)

        seeded = list(entities or [])
        seen = {
            self._canonical_key(
                item.get("name")
                or item.get("entity_name")
                or item.get("entity")
                or item.get("label")
                or ""
            )
            for item in seeded
            if isinstance(item, dict)
        }

        for candidate in primary_candidates:
            key = self._canonical_key(candidate)
            if not key or key in seen:
                continue
            seeded.append(
                {
                    "name": candidate,
                    "entity_name": candidate,
                    "entity": candidate,
                    "label": candidate,
                    "type": "Unknown",
                    "class": "Unknown",
                    "score": 0.95,
                    "source_text": f"{h1} {title}".strip(),
                    "_synthetic_primary_candidate": True,
                    "_detail_priority_seed": True,
                    "sourceUrl": url,
                }
            )
            seen.add(key)
        return seeded

    def _build_detail_primary_fallback(
        self,
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
    ) -> List[Dict[str, Any]]:
        page_signals = page_signals or {}
        candidates = self._extract_primary_page_entity_candidates(
            title=page_signals.get("title") or "",
            h1=page_signals.get("h1") or "",
        )
        fallback = []
        seen = set()
        for candidate in candidates:
            key = self._canonical_key(candidate)
            if not key or key in seen:
                continue
            fallback.append(
                {
                    "name": candidate,
                    "entity_name": candidate,
                    "entity": candidate,
                    "label": candidate,
                    "type": "Unknown",
                    "class": "Unknown",
                    "score": 1.0,
                    "source_text": " ".join(
                        x
                        for x in [
                            page_signals.get("h1") or "",
                            page_signals.get("title") or "",
                            (page_text or "")[:500],
                        ]
                        if x
                    ).strip(),
                    "_detail_primary_fallback": True,
                    "sourceUrl": url,
                }
            )
            seen.add(key)
        return fallback

    def _ensure_route_parent_entity(
        self,
        entities: List[Dict[str, Any]],
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
    ) -> List[Dict[str, Any]]:
        seeded = [dict(entity) for entity in entities or [] if isinstance(entity, dict)]
        page_signals = page_signals or {}
        if not self._is_route_like_page(page_signals=page_signals, url=url):
            return seeded

        route_like_class = choose_route_like_class(self.valid_classes)
        route_class = route_like_class if route_like_class != "Unknown" else "Route"
        route_name_candidates: List[str] = []
        for raw in (
            page_signals.get("h1") or "",
            page_signals.get("title") or "",
            page_signals.get("pageSubject") or "",
        ):
            cleaned = self._clean_route_parent_name(raw)
            if cleaned:
                route_name_candidates.append(cleaned)

        slug_candidate = self._extract_url_slug(url)
        if slug_candidate:
            route_name_candidates.append(self._clean_route_parent_name(slug_candidate.replace("-", " ").replace("_", " ")))

        subject_name = ""
        if route_name_candidates:
            def _route_name_score(value: str) -> tuple:
                norm = self._normalized_for_match(value)
                has_anchor = 1 if any(term in norm for term in ("ruta", "camino", "itinerario", "via verde", "dias", "días")) else 0
                return (has_anchor, len(value))

            subject_name = sorted(route_name_candidates, key=_route_name_score, reverse=True)[0]

        if not subject_name:
            return seeded

        subject_key = self._canonical_key(subject_name)
        for entity in seeded:
            name = self._clean_candidate_name(
                entity.get("name")
                or entity.get("entity_name")
                or entity.get("entity")
                or entity.get("label")
                or ""
            )
            name_key = self._canonical_key(name)
            entity_type = self._normalized_for_match(entity.get("class") or entity.get("type") or "")
            if entity_type == "route" and (name_key == subject_key or subject_key in name_key or name_key in subject_key):
                return seeded

        seeded.insert(
            0,
            {
                "name": subject_name,
                "entity_name": subject_name,
                "entity": subject_name,
                "label": subject_name,
                "type": route_class,
                "class": route_class,
                "score": 1.0,
                "source_text": " ".join(
                    x
                    for x in [
                        page_signals.get("h1") or "",
                        page_signals.get("title") or "",
                        (page_text or "")[:800],
                    ]
                    if x
                ).strip(),
                "_synthetic_primary_candidate": True,
                "_route_parent_seed": True,
                "sourceUrl": url,
            },
        )
        return seeded

    def _clean_route_child_name(self, name: str) -> str:
        text = self._clean_candidate_name(name)
        if not text:
            return ""

        text = re.sub(r"\s*/\s*(Derecha|Izquierda)\b.*$", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\bDistancia\b.*$", "", text, flags=re.IGNORECASE).strip(" -|,;:")
        text = re.sub(r"^(D[IÍ]A\s*\d+|Mañana|Tarde)\b[:\-]?\s*", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(
            r"\b(Saber|Ir|Qué|Que|Tradiciones|Recomendaciones|Descubrir|Descubre)\b$",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip(" -|,;:")

        parts = [part.strip() for part in re.split(r"\s{2,}", text) if part.strip()]
        if parts:
            text = parts[0]

        tokens = text.split()
        if len(tokens) >= 2 and tokens[0].lower() == "de":
            text = " ".join(tokens[1:]).strip()
            tokens = text.split()
        if len(tokens) >= 3 and tokens[-1].lower() in {"palacio", "parque", "catedral", "iglesia", "museo"}:
            text = " ".join(tokens[:-1]).strip()

        return text.strip(" -|,;:")

    def _normalize_route_children(
        self,
        entities: List[Dict[str, Any]],
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ) -> List[Dict[str, Any]]:
        normalized = [dict(entity) for entity in entities or [] if isinstance(entity, dict)]
        if not self._is_route_like_page(page_signals=page_signals, url=url):
            return normalized

        for entity in normalized:
            entity_type = self._normalized_for_match(entity.get("class") or entity.get("type") or "")
            if entity_type == "route":
                continue

            cleaned = self._clean_route_child_name(
                entity.get("name")
                or entity.get("entity_name")
                or entity.get("entity")
                or entity.get("label")
                or ""
            )
            if cleaned:
                entity["name"] = cleaned
                entity["entity_name"] = cleaned
                entity["label"] = cleaned
                entity["entity"] = cleaned

        return normalized

    def _looks_like_technical_noise_entity(self, entity_name: str) -> bool:
        name = self._normalized_for_match(entity_name)
        technical_terms = {
            "tecnologia",
            "tecnologias",
            "agroalimentaria",
            "agroalimentarias",
            "infraestructura",
            "infraestructuras",
            "investigacion",
            "innovacion",
            "desarrollo",
            "biotecnologia",
            "laboratorio",
        }
        hits = sum(1 for term in technical_terms if term in name)
        return hits >= 1 and not any(anchor in name for anchor in ("mercado", "festival", "museo", "ruta", "plaza", "ayuntamiento"))

    def _is_subordinate_event_label(self, entity_name: str, primary_candidates: Optional[List[str]] = None) -> bool:
        name = self._normalized_for_match(entity_name)
        if not name:
            return False

        parent_has_event = any("festival" in self._normalized_for_match(candidate) for candidate in (primary_candidates or []))
        subordinate_terms = {"espectaculos", "programacion", "ciclo", "seccion", "escena", "agenda", "actividades"}
        return parent_has_event and any(term in name for term in subordinate_terms) and "festival" not in name

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
            "contacto",
            "google maps",
            "abrir en google maps",
            "facebook instagram",
            "familias si",
            "consignas mapas",
            "reserva tu actividad",
            "ir al contenido",
            "pago recomendado",
        ]
        if any(term in name for term in bad_terms):
            return True
        if self._looks_like_technical_noise_entity(entity_name):
            return True
        return False

    def _has_strong_tourism_anchor(self, entity_name: str) -> bool:
        name = self._normalized_for_match(entity_name)
        strong_anchors = {
            "festival", "mercado", "museo", "catedral", "iglesia", "capilla", "castillo",
            "palacio", "plaza", "ayuntamiento", "parque", "jardin", "puente", "ruta",
            "camino", "feria", "baluarte", "ciudadela", "estacion", "oficina de turismo",
            "monasterio", "convento", "teatro", "auditorio",
        }
        return any(anchor in name for anchor in strong_anchors)

    def _looks_like_route_entity_name(self, entity_name: str) -> bool:
        name = self._normalized_for_match(entity_name)
        if not name:
            return False
        strong_terms = (
            "ruta ", "camino ", "camino de ", "eurovelo", "cicloturismo",
            "via verde", "sendero", "itinerario",
        )
        return any(term in name for term in strong_terms)

    def _is_abstract_topic_entity(self, entity_name: str) -> bool:
        name = self._normalized_for_match(entity_name)
        abstract_terms = {
            "sostenibilidad", "turistica", "turistico", "produccion", "agraria",
            "ecologica", "agroalimentaria", "agroalimentarias", "plan", "estrategia",
            "modelo", "desarrollo", "innovacion", "tecnologia", "tecnologias",
        }
        hits = sum(1 for term in abstract_terms if term in name)
        return hits >= 2 and not self._has_strong_tourism_anchor(entity_name)

    def _rescue_empty_page_candidates(
        self,
        entities,
        listing_like_page: bool = False,
        detail_priority_page: bool = False,
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ):
        rescued = []
        seen = set()

        for item in entities or []:
            if not isinstance(item, dict):
                continue

            candidate = dict(item)
            name = self._clean_candidate_name(
                candidate.get("name")
                or candidate.get("entity_name")
                or candidate.get("entity")
                or candidate.get("label")
                or ""
            )
            if not name:
                continue
            if self._looks_like_ui_or_category_name(name):
                continue
            if self._is_contextual_noise_entity(name):
                continue
            if self._is_abstract_topic_entity(name):
                continue
            if self._is_narrative_side_entity(name, page_signals=page_signals, url=url):
                continue
            if detail_priority_page and self._is_detail_secondary_label(name, page_signals=page_signals, url=url):
                continue
            if self._is_phrase_fragment(name) and not self._has_strong_tourism_anchor(name):
                continue
            if self._looks_like_bad_compound_entity(name) and not self._has_strong_tourism_anchor(name):
                continue

            key = self._canonical_key(name)
            if not key or key in seen:
                continue

            score = float(candidate.get("score", 0.0) or 0.0)
            primary_match = self._is_primary_page_candidate_name(name, page_signals=page_signals, url=url)
            if listing_like_page:
                if not self._has_strong_tourism_anchor(name):
                    continue
            elif detail_priority_page:
                if score < 0.1 and not (self._has_strong_tourism_anchor(name) or primary_match):
                    continue
            elif score < 0.25 and not self._has_strong_tourism_anchor(name):
                continue

            candidate["name"] = name
            candidate["entity_name"] = name
            candidate["label"] = name
            candidate["entity"] = name
            rescued.append(candidate)
            seen.add(key)

        rescued.sort(
            key=lambda item: (
                1 if self._is_primary_page_candidate_name(item.get("name", ""), page_signals=page_signals, url=url) else 0,
                1 if self._has_strong_tourism_anchor(item.get("name", "")) else 0,
                float(item.get("score", 0.0) or 0.0),
            ),
            reverse=True,
        )
        limit = 12 if listing_like_page else (6 if detail_priority_page else 5)
        return rescued[:limit]

    def _annotate_tourism_evidence(
        self,
        entities,
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
    ):
        annotated = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)
            audit = {"score": 0.0, "decision": "unknown", "reasons": []}

            if self.tourism_evidence is not None and hasattr(self.tourism_evidence, "score_entity"):
                try:
                    audit = self.tourism_evidence.score_entity(
                        item,
                        page_url=url,
                        page_signals=page_signals or {},
                    ) or audit
                except Exception:
                    audit = audit

            item["tourism_evidence_audit"] = audit
            item["tourism_evidence_score"] = float(audit.get("score", 0.0) or 0.0)
            annotated.append(item)

        return annotated

    def _supplement_listing_candidates(
        self,
        kept_entities,
        source_entities,
        listing_like_page: bool = False,
        strict_listing_page: bool = False,
    ):
        profile = self._page_capture_profile(
            listing_like_page=listing_like_page,
            strict_listing_page=strict_listing_page,
        )
        rescued = self._rescue_empty_page_candidates(
            source_entities,
            listing_like_page=(listing_like_page or strict_listing_page),
        )

        merged = []
        seen = set()
        for item in list(kept_entities or []) + list(rescued or []):
            if not isinstance(item, dict):
                continue
            key = self._canonical_key(
                item.get("name")
                or item.get("entity_name")
                or item.get("entity")
                or item.get("label")
                or ""
            )
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)

        return merged[: profile["supplement_limit"]]

    def select_primary_entities(self, entities, html="", url="", top_k=3):
        if not entities:
            entities = []

        raw_title = self._extract_page_title(html)
        raw_h1 = self._extract_h1(html)
        title = self._normalized_for_match(raw_title)
        h1 = self._normalized_for_match(raw_h1)
        breadcrumb = self._normalized_for_match(self._extract_breadcrumb_text(html))
        slug = self._normalized_for_match(self._extract_url_slug(url))
        page_signals = self._build_page_signals(html=html, url=url)
        listing_like = self._is_listing_like_page(page_signals=page_signals, page_text=(h1 + " " + title), url=url)
        detail_priority = self._is_detail_priority_page(page_signals=page_signals, url=url)
        primary_candidates = self._extract_primary_page_entity_candidates(title=raw_title, h1=raw_h1)

        scored = []
        seen_names = {
            self._canonical_key(
                entity.get("name")
                or entity.get("entity_name")
                or entity.get("entity")
                or entity.get("label")
                or ""
            )
            for entity in entities
            if isinstance(entity, dict)
        }

        for candidate in primary_candidates:
            key = self._canonical_key(candidate)
            if not key or key in seen_names:
                continue
            entities.append({
                "name": candidate,
                "entity_name": candidate,
                "entity": candidate,
                "label": candidate,
                "type": "Unknown",
                "class": "Unknown",
                "score": 0.8,
                "source_text": f"{raw_h1} {raw_title}".strip(),
                "_synthetic_primary_candidate": True,
            })
            seen_names.add(key)

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            raw_name = (
                entity.get("name")
                or entity.get("entity_name")
                or entity.get("entity")
                or entity.get("label")
                or ""
            )
            name = self._clean_candidate_name(raw_name)
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
            if any(norm_name == self._normalized_for_match(candidate) for candidate in primary_candidates):
                centrality += 6.0
            elif any(norm_name in self._normalized_for_match(candidate) for candidate in primary_candidates):
                centrality += 2.5
            if self._is_contextual_noise_entity(name):
                centrality -= 4.0
            if self._is_subordinate_event_label(name, primary_candidates=primary_candidates):
                centrality -= 5.0
            if detail_priority and self._is_detail_secondary_label(name, page_signals=page_signals, url=url):
                centrality -= 7.0
            if (
                detail_priority
                and entity.get("_synthetic_primary_candidate")
                and self._is_primary_page_candidate_name(name, page_signals=page_signals, url=url)
            ):
                centrality += 4.0

            penalty = self._entity_name_penalty(name, url=url, page_signals=page_signals)
            if listing_like:
                penalty += 2.0

            item = dict(entity)
            item["name"] = name
            item["entity_name"] = name
            item["label"] = name
            item["entity"] = name
            item["_page_centrality_score"] = round(centrality, 3)
            item["_name_penalty"] = round(penalty, 3)
            item["_benchmark_rank_score"] = round(score + centrality - penalty, 3)
            scored.append(item)

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
        signals = {
            "title": self._extract_page_title(html),
            "h1": self._extract_h1(html),
            "breadcrumb": self._extract_breadcrumb_text(html),
            "slug": slug,
            "slug_tokens": [t for t in re.split(r"[\W_]+", (slug or "").lower()) if t],
            "url": url or "",
        }
        signals["pageIntent"] = self._classify_page_intent(
            page_signals=signals,
            page_text=" ".join(
                x for x in [
                    signals.get("title") or "",
                    signals.get("h1") or "",
                    signals.get("breadcrumb") or "",
                ]
                if x
            ),
            url=url,
        )
        signals["pageSubject"] = ""
        signals["pageSubjectClass"] = ""
        signals["pageSubjectConfidence"] = 0.0
        signals["pageSubjectEvidence"] = []
        return signals

    def _get_entity_context(self, entity: Dict[str, Any], page_text: str = "") -> str:
        parts = [
            entity.get("context") or "",
            entity.get("source_text") or "",
            entity.get("short_description") or "",
            entity.get("long_description") or "",
        ]
        context = " ".join(str(x).strip() for x in parts if str(x).strip())
        return context or page_text

    def _looks_like_address_or_contact_name(self, name: str) -> bool:
        value = self._normalized_for_match(name)
        if not value:
            return False
        if any(value.startswith(prefix) for prefix in ("calle ", "plaza ", "avenida ", "avda ", "paseo ", "camino ")):
            return True
        if re.search(r"\b(s/?n|cp\s+\d{3,5}|\d{5})\b", value):
            return True
        return False

    def _infer_relation_hint_from_context(self, entity: Dict[str, Any], page_text: str = "") -> str:
        context = self._normalized_for_match(self._get_entity_context(entity, page_text=page_text))
        if not context:
            return ""

        relation_markers = [
            ("nearby", ("junto a ", "junto al ", "cerca de ", "a pocos kilometros de ")),
            ("located_in", ("en la comarca de ", "en la provincia de ", "en el entorno de ")),
            ("includes", ("incluye ", "incluyen ", "forma parte de ", "pertenece a ")),
            ("editorial_reference", ("que hacer", "planes para inspirarte", "la historia de", "ruta del", "camino del")),
        ]
        for relation, markers in relation_markers:
            if any(marker in context for marker in markers):
                return relation
        return ""

    def _infer_mention_role(
        self,
        entity: Dict[str, Any],
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
    ) -> str:
        page_signals = page_signals or {}
        name = self._clean_candidate_name(
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        )
        if not name:
            return "ui_noise"

        if self._looks_like_ui_or_category_name(name) or self._is_contextual_noise_entity(name):
            return "ui_noise"

        if self._is_primary_page_candidate_name(name, page_signals=page_signals, url=url):
            return "primary_resource"

        if entity.get("_synthetic_primary_candidate") or entity.get("_detail_priority_seed") or entity.get("_detail_primary_fallback"):
            return "primary_resource"

        page_subject = self._clean_candidate_name(page_signals.get("pageSubject") or "")
        subject_norm = self._normalized_for_match(page_subject)
        name_norm = self._normalized_for_match(name)
        if subject_norm and name_norm and (name_norm == subject_norm or name_norm in subject_norm or subject_norm in name_norm):
            return "primary_resource"

        relation_hint = self._infer_relation_hint_from_context(entity, page_text=page_text)
        if relation_hint:
            if relation_hint in {"nearby", "located_in"}:
                return "related_entity"
            if relation_hint == "editorial_reference":
                return "related_entity"

        if self._looks_like_address_or_contact_name(name):
            return "location_context"

        return "standalone_candidate"

    def _annotate_mention_roles(
        self,
        entities: List[Dict[str, Any]],
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
    ) -> List[Dict[str, Any]]:
        annotated = []
        for entity in entities or []:
            if not isinstance(entity, dict):
                continue
            item = dict(entity)
            mention_role = self._infer_mention_role(item, page_signals=page_signals, page_text=page_text, url=url)
            relation_hint = self._infer_relation_hint_from_context(item, page_text=page_text)
            item["mentionRole"] = mention_role
            item["mentionRelation"] = relation_hint or item.get("mentionRelation") or ""
            annotated.append(item)
        return annotated

    def _is_subject_dominant_context_entity(
        self,
        entity: Dict[str, Any],
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
    ) -> bool:
        page_signals = page_signals or {}
        subject_name = self._normalized_for_match(page_signals.get("pageSubject") or "")
        subject_confidence = float(page_signals.get("pageSubjectConfidence") or 0.0)
        if not subject_name or subject_confidence < 0.75:
            return False

        name = self._normalized_for_match(
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        )
        if not name or name == subject_name or name in subject_name or subject_name in name:
            return False

        context = self._normalized_for_match(self._get_entity_context(entity, page_text=page_text))
        if not context or subject_name not in context:
            return False

        strong_context_markers = (
            "que hacer",
            "planes para inspirarte",
            "la historia de",
            "camino del",
            "ruta del",
            "compartir",
            "guardar favorito",
            "eliminar favorito",
            "ir a mis favoritos",
        )
        if not any(marker in context for marker in strong_context_markers):
            return False

        props_support = any(
            entity.get(field)
            for field in ("address", "phone", "email", "relatedUrls", "sourceUrl")
        )
        if props_support:
            return False

        coords = entity.get("coordinates") or {}
        has_coords = isinstance(coords, dict) and coords.get("lat") is not None and coords.get("lng") is not None
        if has_coords and not any(marker in (url or "").lower() for marker in ("ruta", "route", "camino")):
            return False

        return True

    def _apply_conservative_filter(
        self,
        entities,
        page_text: str = "",
        page_signals: Optional[Dict[str, Any]] = None,
        expected_type: Optional[str] = None,
        url: str = "",
    ):
        entities = self._coerce_entities_to_dicts(entities, url=url)

        def context_getter(item):
            return self._get_entity_context(item, page_text=page_text)

        kept, rejected = self.entity_filter.filter(
            entities=entities,
            context_getter=context_getter,
            page_signals=page_signals or {},
            expected_type=expected_type,
        )

        for item in rejected:
            if isinstance(item, dict):
                item["discarded_by_filter"] = True

        return kept

    def _attach_ontology_candidates(self, entities, page_text: str = "", expected_type=None):
        enriched = []

        if self.ontology_matcher is None or not hasattr(self.ontology_matcher, "match"):
            for entity in entities or []:
                if not isinstance(entity, dict):
                    continue
                item = dict(entity)
                item["ontology_candidates"] = []
                item["ontology_match"] = None
                item["ontology_score"] = None
                enriched.append(item)
            return enriched

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)

            name = (
                item.get("name")
                or item.get("entity_name")
                or item.get("entity")
                or item.get("label")
                or ""
            )

            context = self._get_entity_context(item, page_text=page_text)
            evidence_score = float((item.get("filter_audit") or {}).get("score") or 0.0)
            evidence_score += max(0.0, float(item.get("tourism_evidence_score", 0.0) or 0.0) * 0.35)

            try:
                matches = self.ontology_matcher.match(
                    name,
                    context=context,
                    expected_type=expected_type,
                    evidence_score=evidence_score,
                )
            except TypeError:
                try:
                    matches = self.ontology_matcher.match(name, context=context)
                except Exception:
                    matches = []
            except Exception:
                matches = []

            if matches is None:
                matches = []

            item["ontology_candidates"] = matches

            if matches and isinstance(matches, list) and isinstance(matches[0], dict):
                item["ontology_match"] = matches[0]
                item["ontology_score"] = matches[0].get("score")
            else:
                item["ontology_match"] = None
                item["ontology_score"] = None

            enriched.append(item)

        return enriched

    def _apply_quality_gate(
        self,
        entities,
        page_signals: Optional[Dict[str, Any]] = None,
        url: str = "",
        listing_like_page: bool = False,
        strict_listing_page: bool = False,
        detail_priority_page: bool = False,
    ):
        gated = []
        profile = self._page_capture_profile(
            listing_like_page=listing_like_page,
            strict_listing_page=strict_listing_page,
            detail_priority_page=detail_priority_page,
        )
        for entity in entities or []:
            if not isinstance(entity, dict):
                continue
            item = dict(entity)
            tourism_audit = item.get("tourism_evidence_audit")
            if not isinstance(tourism_audit, dict):
                tourism_audit = {"score": 0.0, "decision": "unknown", "reasons": []}

            quality = self.quality_scorer.evaluate(item, page_url=url, page_signals=page_signals or {})
            item["quality_audit"] = quality

            quality_score = float(quality.get("score", 0.0) or 0.0)
            tourism_score = float(tourism_audit.get("score", 0.0) or 0.0)
            combined_score = round(quality_score + max(0.0, tourism_score) * 0.6, 3)

            keep = quality.get("decision") != "discard"
            if not keep:
                has_anchor = self._has_strong_tourism_anchor(item.get("name", ""))
                primary_match = self._is_primary_page_candidate_name(item.get("name", ""), page_signals=page_signals, url=url)
                if (
                    tourism_score >= profile["evidence_rescue_score"]
                    and (has_anchor or (detail_priority_page and primary_match))
                    and not self._is_abstract_topic_entity(item.get("name", ""))
                ):
                    keep = True
                    item["quality_gate_rescued"] = True
                    item["quality_gate_rescue_reason"] = "tourism_evidence"
            elif quality.get("decision") == "review" and profile["quality_review_ok"]:
                item["quality_gate_rescued"] = True
                item["quality_gate_rescue_reason"] = "review_allowed_by_page_profile"

            if not keep:
                continue

            item["evidence_score"] = combined_score
            gated.append(item)
        return gated

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

        return None

    def _extract_first_description(self, entity: Dict[str, Any], page_text: str) -> Dict[str, Any]:
        result = self._safe_call_component(
            self.description_extractor,
            ["extract"],
            entity,
            page_text,
        )

        if isinstance(result, dict):
            cleaned = {}
            for key, value in result.items():
                if key in {"description", "short_description", "long_description"}:
                    cleaned[key] = strip_sitewide_footer_text(value)
                else:
                    cleaned[key] = value
            return cleaned

        if isinstance(result, str) and result.strip():
            text = strip_sitewide_footer_text(result.strip())
            return {
                "description": text,
                "short_description": text[:220],
                "long_description": text,
            }

        return {}

    def _build_entity_enrichment_context(self, entity: Dict[str, Any], page_text: str = "") -> str:
        item = entity if isinstance(entity, dict) else {}
        parts: List[str] = []
        seen = set()

        def add_part(value: Any) -> None:
            text = strip_sitewide_footer_text(str(value or "").strip())
            if not text:
                return
            key = self._canonical_key(text)
            if key and key not in seen:
                seen.add(key)
                parts.append(text)

        signals = item.get("html_context_signals")
        if isinstance(signals, dict):
            add_part(signals.get("heading"))
            add_part(signals.get("link_text"))

        add_part(item.get("source_text"))
        add_part(item.get("context"))

        merged = " ".join(parts).strip()
        if len(merged) >= 140:
            return merged

        name = str(item.get("name") or item.get("entity_name") or item.get("label") or "").strip()
        is_route_like_entity = self._looks_like_route_entity_name(name)
        is_primary_seed = bool(
            item.get("_synthetic_primary_candidate")
            or item.get("_detail_priority_seed")
            or item.get("_detail_primary_fallback")
        )

        if (is_route_like_entity or is_primary_seed) and page_text:
            add_part(page_text[:1200])
            return " ".join(parts).strip()

        return merged or strip_sitewide_footer_text(page_text[:800] if page_text else "")

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

    def _extract_entity_images(self, entity_name: str, html: str, url: str, block_text: str = "") -> Dict[str, Any]:
        payload: Dict[str, Any] = {}

        enriched = self._safe_call_component(
            self.image_enricher,
            ["enrich"],
            entity=entity_name,
            text=block_text,
            html=html,
            url=url,
        )

        if isinstance(enriched, dict):
            image = str(enriched.get("image") or "").strip()
            main_image = str(enriched.get("mainImage") or "").strip()
            images = enriched.get("images") if isinstance(enriched.get("images"), list) else []
            images = [str(img).strip() for img in images if str(img).strip()]

            if image:
                payload["image"] = image
            if main_image:
                payload["mainImage"] = main_image
            if images:
                payload["images"] = images
            if isinstance(enriched.get("additionalImages"), list):
                payload["additionalImages"] = [str(img).strip() for img in enriched.get("additionalImages") if str(img).strip()]
            if enriched.get("candidateImage"):
                payload["candidateImage"] = str(enriched.get("candidateImage")).strip()

            if payload:
                return payload

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

        if not img:
            return {}

        return {
            "image": img,
            "mainImage": img,
            "images": [img],
        }

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

    def _has_valid_coordinates(self, coords: Any) -> bool:
        if not isinstance(coords, dict):
            return False
        return coords.get("lat") is not None and coords.get("lng") is not None

    def _coords_in_expected_scope(self, lat: Any, lng: Any, source_url: str = "") -> bool:
        try:
            lat_f = float(lat)
            lng_f = float(lng)
        except Exception:
            return False

        if not (-90 <= lat_f <= 90 and -180 <= lng_f <= 180):
            return False

        source = str(source_url or "").lower()
        if "visitaburgosciudad.es" in source:
            return 41.2 <= lat_f <= 43.4 and -4.6 <= lng_f <= -2.5

        return True

    def _is_geocoding_name_safe(self, name: str, entity_type: str = "") -> bool:
        text = self._clean_candidate_name(name)
        key = self._canonical_key(text)
        if not key:
            return False

        tokens = [tok for tok in key.split() if tok]
        if len(tokens) < 2:
            return False

        trailing_fragments = {
            "de", "del", "la", "el", "los", "las", "y", "en", "para", "por",
            "paseo", "ruta", "rutas", "parque", "plaza", "mercado", "museo",
            "palacio", "iglesia", "catedral", "convento", "albergues",
            "apartamentos", "alojamientos", "eventos",
        }
        if tokens[-1] in trailing_fragments:
            return False

        generic_exact = {
            "parque natural",
            "plaza huerto",
            "rutas urbanas",
            "eventos en burgos",
            "albergues",
            "alojamientos en burgos",
            "alojamientos hoteleros",
            "apartamentos turisticos",
            "apartamentos turÇðsticos",
            "centro de aves",
            "cordillera cantabrica",
            "cordillera cantÇ­brica",
            "sistema iberico",
            "sistema ibÇ¸rico",
            "orientacion parque",
            "orientaciÇün parque",
            "espolon parque",
            "espolÇün parque",
            "quinta parque",
            "mercado mayor",
            "muralla la ciudad",
            "iglesia en burgos",
        }
        if key in generic_exact:
            return False

        entity_type_l = str(entity_type or "").strip().lower()
        if entity_type_l in {"hotel", "restaurant", "traditionalmarket"}:
            return any(marker in key for marker in ("hotel", "hostal", "restaurante", "mercado", "burgos"))

        return True

    def _geo_resolver_class_hint(self, entity_type: str) -> str:
        value = str(entity_type or "").strip().lower()
        if value in {"hotel", "restaurant", "bar", "traditionalmarket", "shop"}:
            return "Organization"
        if value in {"route", "event", "person", "concept", "thing", "unknown", ""}:
            return ""
        return "Place"

    def _is_geo_candidate_entity(self, entity: Dict[str, Any]) -> bool:
        entity_type = str(entity.get("class") or entity.get("type") or "").strip().lower()
        allowed_types = {
            "townhall",
            "cathedral",
            "church",
            "museum",
            "palace",
            "castle",
            "square",
            "garden",
            "stadium",
            "hotel",
            "restaurant",
            "traditionalmarket",
            "monument",
            "bridge",
            "wall",
            "gate",
            "naturalresource",
            "historicalorculturalresource",
        }
        if entity_type not in allowed_types:
            return False
        name = str(entity.get("name") or entity.get("entity_name") or "").strip()
        if not name:
            return False
        return True

    def _resolve_missing_coordinates(
        self,
        item: Dict[str, Any],
        props: Dict[str, Any],
        fallback_url: str,
    ) -> Dict[str, Any]:
        coords = item.get("coordinates")
        source_url = item.get("sourceUrl") or fallback_url
        if self._has_valid_coordinates(coords):
            if self._coords_in_expected_scope(coords.get("lat"), coords.get("lng"), source_url):
                return coords
            return {"lat": None, "lng": None}
        if not self._is_geocoding_name_safe(
            item.get("name") or item.get("entity_name") or item.get("label") or "",
            item.get("class") or item.get("type") or "",
        ):
            return coords if isinstance(coords, dict) else {"lat": None, "lng": None}
        if not self.geo_resolver or not self._is_geo_candidate_entity(item):
            return coords if isinstance(coords, dict) else {"lat": None, "lng": None}

        name = str(item.get("name") or item.get("entity_name") or item.get("label") or "").strip()
        if not name:
            return {"lat": None, "lng": None}

        address = ""
        if isinstance(props, dict):
            address = str(
                props.get("address")
                or props.get("streetAddress")
                or props.get("location")
                or ""
            ).strip()

        try:
            resolved = self.geo_resolver.resolve(
                entity_name=name,
                address=address,
                source_url=item.get("sourceUrl") or fallback_url,
                entity_class=self._geo_resolver_class_hint(item.get("class") or item.get("type")),
            )
        except Exception:
            resolved = {}

        lat = resolved.get("lat")
        lng = resolved.get("lng")
        if lat is None or lng is None:
            return coords if isinstance(coords, dict) else {"lat": None, "lng": None}
        if not self._coords_in_expected_scope(lat, lng, source_url):
            return {"lat": None, "lng": None}

        merged = {"lat": float(lat), "lng": float(lng)}

        if resolved.get("wikidata_id") and not item.get("wikidata_id"):
            item["wikidata_id"] = resolved["wikidata_id"]

        existing_props = item.get("properties")
        if not isinstance(existing_props, dict):
            existing_props = {}
        existing_props["geo_source"] = resolved.get("source") or "hybrid_geo_resolver"
        if resolved.get("query"):
            existing_props["geo_query"] = resolved.get("query")
        item["properties"] = existing_props

        return merged

    def _build_enriched_entity(self, entity: Dict[str, Any], html: str, page_text: str, url: str) -> Dict[str, Any]:
        item = dict(entity)

        name = (
            item.get("name")
            or item.get("entity_name")
            or item.get("entity")
            or item.get("label")
            or ""
        ).strip()
        name = self._clean_candidate_name(name)

        item["name"] = name
        item["entity_name"] = name
        item["label"] = name
        item["entity"] = name

        entity_type = str(item.get("class") or item.get("type") or "").strip()

        if entity_type.lower() in {"", "thing", "unknown", "entity", "item", "person"}:
            guessed = self._guess_type_from_name_and_context(
                entity_name=name,
                page_text=page_text,
                current_type="",
            )
            entity_type = guessed or "Unknown"
            item["class"] = entity_type
            item["type"] = entity_type

        entity_context_text = self._build_entity_enrichment_context(item, page_text=page_text)
        if entity_context_text:
            item["context"] = entity_context_text

        description_data = self._extract_first_description(
            entity=item,
            page_text=entity_context_text,
        )

        description_text = (
            str(description_data.get("description") or "").strip()
            or str(description_data.get("short_description") or "").strip()
            or str(description_data.get("long_description") or "").strip()
        )

        props = self._extract_entity_properties(
            entity=item,
            html=html,
            page_text=entity_context_text,
            url=url,
        )

        wikidata_entity_type = str(item.get("wikidata_class_hint") or entity_type).strip()

        wikidata_id = self._extract_wikidata_id(
            entity_name=name,
            entity_type=wikidata_entity_type,
            description=description_text,
            url=url,
        )

        image_data = self._extract_entity_images(
            entity_name=name,
            html=html,
            url=url,
            block_text=entity_context_text[:1000],
        )

        coordinates = self._extract_coordinates_from_props(props)

        if image_data.get("image"):
            item["image"] = image_data["image"]
        if image_data.get("mainImage"):
            item["mainImage"] = image_data["mainImage"]
        if image_data.get("images"):
            item["images"] = image_data["images"]
        if image_data.get("additionalImages"):
            item["additionalImages"] = image_data["additionalImages"]
        if image_data.get("candidateImage"):
            item["candidateImage"] = image_data["candidateImage"]

        if description_data:
            for k, v in description_data.items():
                if v not in (None, "", [], {}):
                    if k in {"description", "short_description", "long_description"}:
                        item[k] = compact_entity_description(v, entity_name=name)
                    else:
                        item[k] = v

        description_text = compact_entity_description(description_text, entity_name=name)
        if description_text:
            item["description"] = description_text
        elif item.get("description"):
            item["description"] = compact_entity_description(item.get("description"), entity_name=name)

        if wikidata_id:
            item["wikidata_id"] = wikidata_id

        if props:
            existing_props = item.get("properties")
            if not isinstance(existing_props, dict):
                existing_props = {}
            existing_props.update(props)
            item["properties"] = existing_props

            if image_data.get("image") and not existing_props.get("image"):
                existing_props["image"] = image_data["image"]
            if image_data.get("mainImage") and not existing_props.get("mainImage"):
                existing_props["mainImage"] = image_data["mainImage"]
            if image_data.get("additionalImages") and not existing_props.get("additionalImages"):
                existing_props["additionalImages"] = image_data["additionalImages"]
            if image_data.get("candidateImage") and not existing_props.get("candidateImage"):
                existing_props["candidateImage"] = image_data["candidateImage"]

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

        if not self._has_valid_coordinates(item.get("coordinates")):
            item["coordinates"] = self._resolve_missing_coordinates(
                item=item,
                props=item.get("properties") if isinstance(item.get("properties"), dict) else props,
                fallback_url=url,
            )
            if item["coordinates"].get("lat") is not None:
                item["latitude"] = item["coordinates"]["lat"]
            if item["coordinates"].get("lng") is not None:
                item["longitude"] = item["coordinates"]["lng"]

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

    def _apply_final_filter(
        self,
        entities,
        page_signals: Optional[Dict[str, Any]] = None,
        page_text: str = "",
        url: str = "",
        listing_like_page: bool = False,
        detail_priority_page: bool = False,
    ):
        prekept = []
        prerejected = []
        route_like_page = self._is_route_like_page(page_signals=page_signals, url=url)

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
            name = self._clean_candidate_name(name)
            item["name"] = name
            item["entity_name"] = name
            item["label"] = name
            item["entity"] = name

            reasons = []
            penalty = self._entity_name_penalty(name, url=url, page_signals=page_signals)
            primary_match = self._is_primary_page_candidate_name(name, page_signals=page_signals, url=url)

            if self._looks_like_ui_or_category_name(name):
                reasons.append("ui_or_category_name")
            if self._looks_like_bad_compound_entity(name):
                reasons.append("bad_compound_name")
            if self._is_contextual_noise_entity(name):
                reasons.append("contextual_noise_name")
            if self._is_narrative_side_entity(name, page_signals=page_signals, url=url):
                reasons.append("narrative_side_entity")
            if self._is_subject_dominant_context_entity(item, page_signals=page_signals, page_text=page_text, url=url):
                reasons.append("page_subject_context_reference")
            mention_role = str(item.get("mentionRole") or "").strip().lower()
            if mention_role == "ui_noise":
                reasons.append("mention_role_ui_noise")
            if mention_role == "location_context":
                reasons.append("mention_role_location_context")
            if mention_role == "related_entity" and not listing_like_page and not route_like_page:
                reasons.append("mention_role_related_entity")
            if self._is_phrase_fragment(name):
                reasons.append("phrase_fragment")
            if detail_priority_page and self._is_detail_secondary_label(name, page_signals=page_signals, url=url):
                reasons.append("detail_secondary_label")
            if (
                listing_like_page
                and len(self._tokenize_name(name)) >= 7
                and not self._has_strong_tourism_anchor(name)
            ):
                reasons.append("listing_page_long_compound")

            entity_type = str(item.get("class") or item.get("type") or "").strip().lower()
            current_path = (urlparse(url).path or "/").rstrip("/") or "/"
            homepage_like = current_path in {"/", "/es"}
            if entity_type in {"unknown", ""} and penalty >= 3:
                reasons.append("weak_type_and_bad_name")
            if entity_type == "route" and not self._looks_like_route_entity_name(name):
                reasons.append("weak_route_name")
            if entity_type == "route" and homepage_like and not detail_priority_page:
                reasons.append("homepage_context_route")

            route_parent_candidate = (
                route_like_page
                and entity_type == "route"
                and (
                    primary_match
                    or item.get("_synthetic_primary_candidate")
                    or item.get("_route_parent_seed")
                    or item.get("_detail_primary_fallback")
                )
            )
            if route_parent_candidate:
                reasons = [
                    reason
                    for reason in reasons
                    if reason not in {
                        "bad_compound_name",
                        "phrase_fragment",
                        "weak_type_and_bad_name",
                        "weak_route_name",
                        "mention_role_related_entity",
                    }
                ]
                penalty = max(0.0, penalty - 4.0)

            if detail_priority_page and primary_match:
                reasons = [
                    reason
                    for reason in reasons
                    if reason not in {"bad_compound_name", "phrase_fragment", "weak_type_and_bad_name"}
                ]
                penalty = max(0.0, penalty - 3.0)

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
            else:
                prekept.append(item)

        kept, rejected = self.final_filter.filter(prekept) if self.final_filter else (prekept, [])

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

    def run(self, html: str, url: str = "", expected_type: Optional[str] = None):
        html = self._scalar_text(html)
        if not html and url:
            html = self._fetch_html(url)

        early_signals = self._build_page_signals(html=html, url=url)
        if self._should_ignore_page(page_signals=early_signals, url=url):
            if self.debug:
                print(
                    f"[PIPELINE] ignored_page intent={early_signals.get('pageIntent')} url={url}",
                    file=sys.stderr,
                )
            return []

        if self.block_extractor is None:
            return []

        try:
            blocks = self.block_extractor.extract(html)
        except Exception:
            return []

        page_text = self._extract_text(blocks)
        page_signals = self._build_page_signals(html=html, url=url)
        page_signals["pageIntent"] = self._classify_page_intent(
            page_signals=page_signals,
            page_text=page_text,
            url=url,
        )
        page_subject = self._detect_page_subject(
            page_signals=page_signals,
            page_text=page_text,
            url=url,
        )
        page_signals["pageSubject"] = page_subject.get("name") or ""
        page_signals["pageSubjectClass"] = page_subject.get("class") or ""
        page_signals["pageSubjectConfidence"] = float(page_subject.get("confidence") or 0.0)
        page_signals["pageSubjectEvidence"] = page_subject.get("evidence") or []

        strict_listing_page = self._is_strict_listing_page(
            page_signals=page_signals,
            page_text=page_text,
            url=url,
        )

        listing_like_page = self._is_listing_like_page(
            page_signals=page_signals,
            page_text=page_text,
            url=url,
        )
        detail_priority_page = self._is_detail_priority_page(page_signals=page_signals, url=url)
        route_like_page = self._is_route_like_page(page_signals=page_signals, url=url)

        if self.entity_extractor is None:
            return []

        try:
            entities = self.entity_extractor.extract(blocks)
        except Exception:
            return []

        self._debug_stage("extract", entities)

        entities = self._coerce_entities_to_dicts(entities, url=url)
        if detail_priority_page or route_like_page:
            entities = self._seed_detail_primary_candidates(
                entities,
                page_signals=page_signals,
                url=url,
            )
        self._debug_stage("extract_coerced", entities)

        if self.cleaner is not None and hasattr(self.cleaner, "clean"):
            try:
                entities = self.cleaner.clean(entities)
            except Exception:
                pass
        self._debug_stage("clean", entities)

        entities = self._coerce_entities_to_dicts(entities, url=url)

        if self.deduplicator is not None and hasattr(self.deduplicator, "deduplicate"):
            try:
                entities = self.deduplicator.deduplicate(entities)
            except Exception:
                pass
        self._debug_stage("deduplicate", entities)

        entities = self._coerce_entities_to_dicts(entities, url=url)

        if self.normalizer is not None and hasattr(self.normalizer, "normalize"):
            try:
                entities = self.normalizer.normalize(entities)
            except Exception:
                pass
        self._debug_stage("normalize", entities)

        entities = self._coerce_entities_to_dicts(entities, url=url)

        if self.expander is not None and hasattr(self.expander, "expand"):
            try:
                entities = self.expander.expand(entities, page_text)
            except TypeError:
                try:
                    entities = self.expander.expand(entities, text=page_text)
                except Exception:
                    pass
            except Exception:
                pass
        self._debug_stage("expand", entities)

        entities = self._coerce_entities_to_dicts(entities, url=url)

        if self.splitter is not None and hasattr(self.splitter, "split"):
            try:
                entities = self.splitter.split(entities)
            except Exception:
                pass
        self._debug_stage("split", entities)

        split_entities = self._coerce_entities_to_dicts(list(entities or []), url=url)
        self._debug_stage("split_coerced", split_entities)

        entities = split_entities
        if self.entity_filter is not None and hasattr(self.entity_filter, "filter"):
            try:
                entities = self._apply_conservative_filter(
                    split_entities,
                    page_text=page_text,
                    page_signals=page_signals,
                    expected_type=expected_type,
                    url=url,
                )
            except Exception:
                entities = split_entities

        if not entities and split_entities and not strict_listing_page:
            if self.debug:
                print(
                    f"[PIPELINE] conservative_filter_bypassed_on_empty for {url}: split={len(split_entities)}",
                    file=sys.stderr,
                )
            entities = split_entities

        entities = self._coerce_entities_to_dicts(entities, url=url)
        entities = self._sanitize_entities_for_downstream(entities)
        self._debug_stage("conservative_filter", entities)

        try:
            entities = self._annotate_tourism_evidence(
                entities,
                page_signals=page_signals,
                url=url,
            )
        except Exception:
            pass

        if listing_like_page or strict_listing_page:
            try:
                entities = self._supplement_listing_candidates(
                    entities,
                    split_entities,
                    listing_like_page=listing_like_page,
                    strict_listing_page=strict_listing_page,
                )
            except Exception:
                pass

        entities = self._coerce_entities_to_dicts(entities, url=url)
        entities = self._sanitize_entities_for_downstream(entities)
        self._debug_stage("tourism_evidence", entities)

        try:
            entities = self._attach_ontology_candidates(
                entities,
                page_text=page_text,
                expected_type=expected_type,
            )
        except Exception:
            pass

        entities = self._coerce_entities_to_dicts(entities, url=url)

        try:
            entities = self._ensure_entity_type(
                entities,
                page_text=page_text,
                page_signals=page_signals,
                expected_type=expected_type,
            )
        except Exception:
            pass

        entities = self._coerce_entities_to_dicts(entities, url=url)
        self._debug_stage("typed_candidates", entities)

        candidates = entities
        if self.semantic_matcher is not None and hasattr(self.semantic_matcher, "match"):
            try:
                candidates = self.semantic_matcher.match(entities, page_text=page_text)
            except TypeError:
                try:
                    candidates = self.semantic_matcher.match(entities)
                except Exception:
                    candidates = entities
            except Exception:
                candidates = entities

        candidates = self._coerce_entities_to_dicts(candidates, url=url)

        try:
            candidates = self._promote_semantic_type(candidates)
        except Exception:
            pass

        try:
            candidates = self._ensure_entity_type(
                candidates,
                page_text=page_text,
                page_signals=page_signals,
                expected_type=expected_type,
            )
        except Exception:
            pass

        if self.quality_scorer is not None and hasattr(self.quality_scorer, "evaluate"):
            try:
                candidates = self._apply_quality_gate(
                    candidates,
                    page_signals=page_signals,
                    url=url,
                    listing_like_page=listing_like_page,
                    strict_listing_page=strict_listing_page,
                    detail_priority_page=detail_priority_page,
                )
            except Exception:
                pass

        candidates = self._coerce_entities_to_dicts(candidates, url=url)
        candidates = self._sanitize_entities_for_downstream(candidates)
        self._debug_stage("semantic_match", candidates)

        ranked_entities = candidates
        if self.ranker is not None and hasattr(self.ranker, "rank"):
            try:
                ranked_entities = self.ranker.rank(
                    candidates=candidates,
                    target_type=expected_type,
                    page_text=page_text,
                )
            except TypeError:
                try:
                    ranked_entities = self.ranker.rank(candidates)
                except Exception:
                    ranked_entities = candidates
            except Exception:
                ranked_entities = candidates

        ranked_entities = self._coerce_entities_to_dicts(ranked_entities, url=url)

        try:
            ranked_entities = self._promote_semantic_type(ranked_entities)
        except Exception:
            pass

        try:
            ranked_entities = self._ensure_entity_type(
                ranked_entities,
                page_text=page_text,
                page_signals=page_signals,
                expected_type=expected_type,
            )
        except Exception:
            pass

        if self.quality_scorer is not None and hasattr(self.quality_scorer, "evaluate"):
            try:
                ranked_entities = self._apply_quality_gate(
                    ranked_entities,
                    page_signals=page_signals,
                    url=url,
                    listing_like_page=listing_like_page,
                    strict_listing_page=strict_listing_page,
                    detail_priority_page=detail_priority_page,
                )
            except Exception:
                pass

        ranked_entities = self._coerce_entities_to_dicts(ranked_entities, url=url)
        ranked_entities = self._sanitize_entities_for_downstream(ranked_entities)
        self._debug_stage("rank", ranked_entities)

        top_k = min(12, max(5, len(ranked_entities) or 5)) if listing_like_page else max(3, min(8, len(ranked_entities) or 3))

        try:
            ranked_entities = self.select_primary_entities(
                ranked_entities,
                html=html,
                url=url,
                top_k=top_k,
            )
        except Exception:
            ranked_entities = ranked_entities[:top_k]

        ranked_entities = self._coerce_entities_to_dicts(ranked_entities, url=url)
        ranked_entities = self._sanitize_entities_for_downstream(ranked_entities)
        self._debug_stage("sanitize_ranked", ranked_entities)

        final_entities = ranked_entities
        if self.llm_supervisor is not None:
            try:
                final_entities = self._apply_llm_supervisor(
                    ranked_entities=ranked_entities,
                    page_text=page_text,
                    url=url,
                )
            except Exception:
                final_entities = ranked_entities

        final_entities = self._coerce_entities_to_dicts(final_entities, url=url)
        final_entities = self._sanitize_entities_for_downstream(final_entities)
        self._debug_stage("llm_supervisor", final_entities)

        try:
            final_entities = self._ensure_entity_type(
                final_entities,
                page_text=page_text,
                page_signals=page_signals,
                expected_type=expected_type,
            )
        except Exception:
            pass

        if self.quality_scorer is not None and hasattr(self.quality_scorer, "evaluate"):
            try:
                final_entities = self._apply_quality_gate(
                    final_entities,
                    page_signals=page_signals,
                    url=url,
                    listing_like_page=listing_like_page,
                    strict_listing_page=strict_listing_page,
                    detail_priority_page=detail_priority_page,
                )
            except Exception:
                pass

        final_entities = self._coerce_entities_to_dicts(final_entities, url=url)
        final_entities = self._sanitize_entities_for_downstream(final_entities)
        self._debug_stage("sanitize_final", final_entities)

        pre_cluster_entities = list(final_entities)
        clustered = pre_cluster_entities

        if self.clusterer is not None and hasattr(self.clusterer, "cluster"):
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

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("cluster", clustered)

        try:
            clustered = self._ensure_entity_type(
                clustered,
                page_text=page_text,
                page_signals=page_signals,
                expected_type=expected_type,
            )
        except Exception:
            pass

        if self.quality_scorer is not None and hasattr(self.quality_scorer, "evaluate"):
            try:
                clustered = self._apply_quality_gate(
                    clustered,
                    page_signals=page_signals,
                    url=url,
                    listing_like_page=listing_like_page,
                    strict_listing_page=strict_listing_page,
                    detail_priority_page=detail_priority_page,
                )
            except Exception:
                pass

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("sanitize_flattened", clustered)

        try:
            clustered = self._ensure_route_parent_entity(
                clustered,
                page_signals=page_signals,
                page_text=page_text,
                url=url,
            )
            clustered = self._normalize_route_children(
                clustered,
                page_signals=page_signals,
                url=url,
            )
        except Exception:
            pass

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("route_parent_seeded", clustered)

        try:
            clustered = self._enrich_final_entities(
                entities=clustered,
                html=html,
                page_text=page_text,
                url=url,
            )
        except Exception:
            pass

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("enriched_final", clustered)

        try:
            clustered = self._annotate_mention_roles(
                clustered,
                page_signals=page_signals,
                page_text=page_text,
                url=url,
            )
        except Exception:
            pass

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("mention_roles", clustered)

        if self.final_filter is not None and hasattr(self.final_filter, "filter"):
            try:
                clustered = self._apply_final_filter(
                    clustered,
                    page_signals=page_signals,
                    page_text=page_text,
                    url=url,
                    listing_like_page=listing_like_page,
                    detail_priority_page=detail_priority_page,
                )
            except Exception:
                pass

        if not clustered and not strict_listing_page:
            rescue_pool = final_entities or ranked_entities or candidates or entities or split_entities
            try:
                clustered = self._rescue_empty_page_candidates(
                    rescue_pool,
                    listing_like_page=listing_like_page,
                    detail_priority_page=detail_priority_page,
                    page_signals=page_signals,
                    url=url,
                )
            except Exception:
                clustered = clustered or []

        if not clustered and detail_priority_page:
            try:
                clustered = self._build_detail_primary_fallback(
                    page_signals=page_signals,
                    page_text=page_text,
                    url=url,
                )
                clustered = self._ensure_entity_type(
                    clustered,
                    page_text=page_text,
                    page_signals=page_signals,
                    expected_type=expected_type,
                )
            except Exception:
                clustered = clustered or []

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("final_filter", clustered)

        if getattr(self, "enable_entity_postprocess", False):
            try:
                clustered = postprocess_entities(
                    clustered,
                    enable_dedupe=getattr(self, "enable_entity_dedupe", True),
                )
            except Exception as e:
                if self.debug:
                    print(f"[POSTPROCESS] failed: {e}", file=sys.stderr)

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("postprocessed_final", clustered)

        try:
            clustered = enforce_closed_world_batch(
                clustered,
                self.valid_classes,
                ontology_catalog=self.ontology_catalog,
            )
        except Exception:
            pass

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("closed_world", clustered)

        try:
            clustered = self._align_entities_with_page_subject(
                clustered,
                page_signals=page_signals,
                url=url,
            )
        except Exception:
            pass

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("page_subject_aligned", clustered)

        try:
            clustered = self._annotate_page_structure(
                clustered,
                page_signals=page_signals,
                url=url,
            )
        except Exception:
            pass

        clustered = self._coerce_entities_to_dicts(clustered, url=url)
        clustered = self._sanitize_entities_for_downstream(clustered)
        self._debug_stage("page_structure", clustered)

        return clustered
