from __future__ import annotations
from pathlib import Path

import os
import sys
import json
import argparse
import certifi
import traceback
import re
import unicodedata
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from typing import Any, Dict, List, Tuple

# Asegura que la raíz del proyecto esté en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


from src.site_crawler import SiteCrawler
from src.tourism_pipeline_ontology_driven import TourismPipeline
from src.knowledge_graph_builder import KnowledgeGraphBuilder
from src.report.markdown_report import EntitiesReporter
from src.entity_description_consolidator import EntityDescriptionConsolidator
from src.export.json_exporter import JSONExporter
from src.visualization.tourism_graph_visualizer import TourismGraphVisualizer
from src.visualization.tourism_map_visualizer import TourismMapVisualizer
from src.kg_postprocessor import KGPostProcessor
from src.entity_resolver import EntityResolver
from src.ontology_utils import (
    OFFICIAL_SEGITTUR_CORE_NT,
    ONTOLOGY_ALIASES,
    enforce_closed_world_batch,
)


os.environ["PYTHONIOENCODING"] = "utf-8"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()
os.environ["SSL_CERT_FILE"] = certifi.where()


def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def diag(enabled, *args, **kwargs):
    if enabled:
        print("[DIAG]", *args, file=sys.stderr, **kwargs)


def safe_json_output(data):
    try:
        print(json.dumps(data, ensure_ascii=False), flush=True)
    except Exception as e:
        error_output = {
            "status": "error",
            "error_type": "json_serialization",
            "message": str(e),
        }
        print(json.dumps(error_output, ensure_ascii=False), flush=True)


class ProgressReporter:
    def __init__(self, total: int = 0, enabled: bool = True, interval_seconds: float = 10.0):
        self.total = max(int(total or 0), 0)
        self.enabled = enabled
        self.interval_seconds = max(float(interval_seconds or 0), 0.0)
        self.started_at = time.time()
        self.last_emit_at = 0.0

    def _format_seconds(self, seconds: float | None) -> str:
        if seconds is None:
            return "--:--:--"
        seconds = max(int(seconds), 0)
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def emit(
        self,
        stage: str,
        current: int | None = None,
        url: str = "",
        entities_count: int | None = None,
        errors_count: int | None = None,
        force: bool = False,
    ) -> None:
        if not self.enabled:
            return

        now = time.time()
        if not force and self.last_emit_at and (now - self.last_emit_at) < self.interval_seconds:
            return

        self.last_emit_at = now
        elapsed = now - self.started_at
        parts = [f"[PROGRESS] {stage}"]

        if current is not None and self.total:
            safe_current = min(max(int(current), 0), self.total)
            percent = (safe_current / self.total) * 100
            avg = elapsed / safe_current if safe_current else None
            eta = (self.total - safe_current) * avg if avg else None
            parts.append(f"page={safe_current}/{self.total}")
            parts.append(f"{percent:.1f}%")
            parts.append(f"elapsed={self._format_seconds(elapsed)}")
            parts.append(f"eta={self._format_seconds(eta)}")
        else:
            parts.append(f"elapsed={self._format_seconds(elapsed)}")

        if entities_count is not None:
            parts.append(f"entities={entities_count}")
        if errors_count is not None:
            parts.append(f"errors={errors_count}")
        if url:
            parts.append(f"url={url}")

        log(" | ".join(parts))


def normalize_class_name(value):
    if not value:
        return None

    if isinstance(value, list):
        value = value[0] if value else None

    if not value:
        return None

    value = str(value).strip()

    if "#" in value:
        value = value.split("#")[-1]
    elif "/" in value:
        value = value.rstrip("/").split("/")[-1]

    return value or None


def has_coordinates(entity):
    coords = entity.get("coordinates") or {}
    return coords.get("lat") is not None and coords.get("lng") is not None


def has_wikidata(entity):
    return bool(
        entity.get("wikidata_id")
        or entity.get("wikidataId")
        or (entity.get("properties") or {}).get("wikidata_id")
        or (entity.get("properties") or {}).get("wikidataId")
    )


def has_image(entity):
    return bool(
        entity.get("image")
        or entity.get("mainImage")
        or (entity.get("properties") or {}).get("image")
        or (entity.get("properties") or {}).get("mainImage")
    )


def compute_entity_stats(global_entities):
    type_counter = Counter()

    with_wikidata = 0
    without_wikidata = 0
    with_coordinates = 0
    without_coordinates = 0
    with_image = 0
    without_image = 0

    entities_by_type = {}

    for entity in global_entities:
        cls = normalize_class_name(entity.get("class") or entity.get("type")) or "Unknown"
        type_counter[cls] += 1

        entity_name = (
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        )
        entities_by_type.setdefault(cls, []).append(entity_name)

        if has_wikidata(entity):
            with_wikidata += 1
        else:
            without_wikidata += 1

        if has_coordinates(entity):
            with_coordinates += 1
        else:
            without_coordinates += 1

        if has_image(entity):
            with_image += 1
        else:
            without_image += 1

    total = len(global_entities)

    by_type_percent = {}
    if total > 0:
        for k, v in type_counter.items():
            by_type_percent[k] = round((v / total) * 100, 2)

    return {
        "total_entities": total,
        "by_type": dict(type_counter),
        "by_type_percent": by_type_percent,
        "entities_by_type": entities_by_type,
        "with_wikidata": with_wikidata,
        "without_wikidata": without_wikidata,
        "with_coordinates": with_coordinates,
        "without_coordinates": without_coordinates,
        "with_image": with_image,
        "without_image": without_image,
    }


def infer_main_prediction(global_entities):
    if not global_entities:
        return None

    class_counter = Counter()
    class_score_sum = {}

    noisy_names = {
        "niña",
        "sevilla academias",
        "bienal espacios",
    }

    noisy_classes = {
        "Concept",
    }

    for entity in global_entities:
        cls = normalize_class_name(entity.get("class") or entity.get("type"))
        if not cls or cls in noisy_classes:
            continue

        name = (
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        ).strip().lower()

        score = entity.get("score", 0) or 0

        if name in noisy_names:
            continue

        if score < 0.6:
            continue

        class_counter[cls] += 1
        class_score_sum[cls] = class_score_sum.get(cls, 0) + score

    if not class_counter:
        return None

    best_class = sorted(
        class_counter.keys(),
        key=lambda c: (class_counter[c], class_score_sum[c]),
        reverse=True
    )[0]

    return best_class


def build_stdout_payload(global_entities, args):
    prediction = infer_main_prediction(global_entities)

    try:
        stats = compute_entity_stats(global_entities)
    except Exception as e:
        stats = {"error": str(e)}

    return {
        "status": "ok",
        "mode": "single_url" if args.url else "crawl",
        "start_url": args.start_url,
        "url": args.url,
        "max_pages": args.max_pages,
        "expected_type": getattr(args, "expected_type", None),
        "entity_count": len(global_entities),
        "prediction": prediction,
        "stats": stats,
        "entities": global_entities,
    }


def build_error_payload(args, message, error_type="pipeline_error", extra=None):
    payload = {
        "status": "error",
        "error_type": error_type,
        "message": str(message),
        "mode": "single_url" if getattr(args, "url", None) else "crawl",
        "start_url": getattr(args, "start_url", None),
        "url": getattr(args, "url", None),
        "max_pages": getattr(args, "max_pages", None),
        "expected_type": getattr(args, "expected_type", None),
        "entity_count": 0,
        "prediction": None,
        "stats": {},
        "entities": [],
    }
    if extra:
        payload.update(extra)
    return payload


def build_parser():
    parser = argparse.ArgumentParser(
        description="Proyecto de extracción ontológica turística"
    )

    parser.add_argument("--start_url", type=str, default="https://www.info.valladolid.es/")
    parser.add_argument("--url", type=str, default=None)
    parser.add_argument("--max_pages", type=int, default=None)
    parser.add_argument("--ontology_path", type=str, default="src/ontology/core.rdf", help="Ruta local, URL RDF/OWL o alias segittur/segittur_core")
    parser.add_argument("--kg_output", type=str, default="knowledge_graph.ttl")
    parser.add_argument("--kg_html_output", type=str, default="knowledge_graph.html")
    parser.add_argument("--report_output", type=str, default="entities_report.md")
    parser.add_argument("--json_output", type=str, default="entities.json")
    parser.add_argument("--graph_html_output", type=str, default="tourism_graph.html")
    parser.add_argument("--map_html_output", type=str, default="tourism_map.html")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--json_stdout", action="store_true")
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--use_fewshots", action="store_true")
    parser.add_argument("--fewshot_file", type=str, default=None)
    parser.add_argument("--expected_type", type=str, default=None)
    parser.add_argument("--no_progress", action="store_true", help="Desactiva las lineas de progreso en stderr")
    parser.add_argument("--progress_interval", type=float, default=10.0, help="Segundos minimos entre actualizaciones de progreso")

    return parser


def load_fewshots(fewshot_file):
    if not fewshot_file:
        return []

    with open(fewshot_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise TypeError("fewshot_file debe contener una lista de ejemplos")

    return data


def build_pipeline(args):
    fewshots = []
    if args.use_fewshots:
        fewshots = load_fewshots(args.fewshot_file)

    return TourismPipeline(
        args.ontology_path,
        use_fewshots=args.use_fewshots,
        fewshots=fewshots,
        benchmark_mode=args.benchmark,
    )


def validate_inputs(args, diagnostic=False):
    ontology_value = str(args.ontology_path or "").strip()

    is_alias = ontology_value in ONTOLOGY_ALIASES
    is_url = ontology_value.startswith("http://") or ontology_value.startswith("https://")
    is_local_file = os.path.exists(ontology_value)

    if not (is_alias or is_url or is_local_file):
        error = {
            "status": "error",
            "error_type": "ontology_not_found",
            "message": f"No existe ni es accesible la ontología indicada: {ontology_value}",
            "url": args.url,
            "start_url": args.start_url,
        }
        diag(diagnostic, f"ERROR ontology_not_found: {error}")
        return error

    return None    


def get_pages_for_url(url, max_pages=1, diagnostic=False):
    crawler = SiteCrawler(url, max_pages=max_pages)
    pages = crawler.crawl()

    diag(diagnostic, f"get_pages_for_url(): páginas recuperadas={len(pages)}")

    if not pages:
        raise ValueError(f"No se pudo obtener contenido para la URL: {url}")

    return pages


def get_pages(args, diagnostic=False):
    if args.url:
        if not args.json_stdout:
            log(f"🌐 Procesando URL única: {args.url}")
        return get_pages_for_url(args.url, max_pages=1, diagnostic=diagnostic)

    if not args.json_stdout:
        log(f"\n🌐 Iniciando crawling del sitio: {args.start_url}\n")

    crawler = SiteCrawler(args.start_url, max_pages=args.max_pages)
    pages = crawler.crawl()

    diag(diagnostic, f"get_pages(): páginas recuperadas={len(pages)}")
    return pages


def process_pages(pages, pipeline, args, diagnostic=False):
    """
    Devuelve resultados por página en formato bloque:
    [
      {"url": ..., "entities": [...]},
      ...
    ]
    """
    results_ok: List[Dict[str, Any]] = []
    page_errors: List[Dict[str, Any]] = []
    progress = ProgressReporter(
        total=len(pages),
        enabled=not getattr(args, "no_progress", False),
        interval_seconds=getattr(args, "progress_interval", 10.0),
    )

    def _processed_entity_count() -> int:
        return sum(len(block.get("entities", []) or []) for block in results_ok)

    progress.emit("start_processing", current=0, force=True)

    for idx, (url, html) in enumerate(pages, start=1):
        progress.emit(
            "processing_page",
            current=idx,
            url=url,
            entities_count=_processed_entity_count(),
            errors_count=len(page_errors),
            force=(idx == 1),
        )

        if diagnostic:
            log(f"\n🔎 Procesando página: {url}")

        diag(diagnostic, f"Página {idx}/{len(pages)}")
        diag(diagnostic, f"HTML length={len(html) if html else 0}")

        try:
            if html:
                soup = BeautifulSoup(html, "html.parser")
                text_preview = soup.get_text(separator=" ", strip=True)
                diag(diagnostic, f"text_preview_len={len(text_preview)}")
                diag(diagnostic, f"text_preview_300={text_preview[:300]}")

            result = pipeline.run(
                html,
                url=url,
                expected_type=getattr(args, "expected_type", None),
            )

            print("  -> ENTITIES_JSON:")
            for i, e in enumerate((result or [])[:3], start=1):
                print(f"     [{i}]")
                print(json.dumps(e, indent=2, ensure_ascii=False))

            print("  -> ENTITIES:")
            for i, e in enumerate((result or [])[:5], start=1):
                print(
                    f"     {i}. name={e.get('name')!r} | "
                    f"type={e.get('type')!r} | "
                    f"semantic_type={e.get('semantic_type')!r} | "
                    f"score={e.get('score')!r}"
                )

            diag(diagnostic, f"Tipo de result={type(result).__name__}")

            if result is None:
                raise ValueError("pipeline.run devolvió None")

            if isinstance(result, list):
                if not result:
                    log(f"ℹ️ Sin entidades finales para {url} (resultado válido tras filtrado)")
                    diag(diagnostic, f"pipeline.run devolvió lista vacía para {url}; se omite sin error")
                    progress.emit(
                        "page_done_empty",
                        current=idx,
                        url=url,
                        entities_count=_processed_entity_count(),
                        errors_count=len(page_errors),
                    )
                    continue

                results_ok.append({
                    "url": url,
                    "entities": result,
                })

            elif isinstance(result, dict):
                if "entities" in result and isinstance(result.get("entities"), list):
                    if not result["entities"]:
                        log(f"ℹ️ Sin entidades finales para {url} (dict con entities vacío, resultado válido tras filtrado)")
                        diag(diagnostic, f"pipeline.run devolvió dict con entities vacío para {url}; se omite sin error")
                        progress.emit(
                            "page_done_empty",
                            current=idx,
                            url=url,
                            entities_count=_processed_entity_count(),
                            errors_count=len(page_errors),
                        )
                        continue
                    block = dict(result)
                    block.setdefault("url", url)
                    results_ok.append(block)
            
                else:
                    results_ok.append({
                        "url": url,
                        "entities": [result],
                    })

            else:
                raise TypeError(f"Tipo de retorno no soportado: {type(result).__name__}")

            progress.emit(
                "page_done",
                current=idx,
                url=url,
                entities_count=_processed_entity_count(),
                errors_count=len(page_errors),
                force=(idx == len(pages)),
            )

        except Exception as exc:
            tb = traceback.format_exc()

            error_record = {
                "url": url,
                "error_type": exc.__class__.__name__,
                "message": str(exc),
                "traceback": tb,
            }
            page_errors.append(error_record)

            log(f"⚠️ Error procesando {url}: {exc}")
            print("----- TRACEBACK BEGIN -----", file=sys.stderr)
            print(tb, file=sys.stderr, end="")
            print("----- TRACEBACK END -----", file=sys.stderr)

            diag(diagnostic, f"Excepción detallada en process_pages(): {repr(exc)}")
            progress.emit(
                "page_error",
                current=idx,
                url=url,
                entities_count=_processed_entity_count(),
                errors_count=len(page_errors),
                force=True,
            )

    progress.emit(
        "processing_done",
        current=len(pages),
        entities_count=_processed_entity_count(),
        errors_count=len(page_errors),
        force=True,
    )
    return results_ok, page_errors


def _normalize_name_for_merge(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    noise_patterns = [
        r"\bcompartir\b",
        r"\babrir\b",
        r"\bgoogle maps\b",
        r"\bdireccion\b",
        r"\bdirección\b",
        r"\bcopiar direccion\b",
        r"\bcopiar dirección\b",
    ]
    for pattern in noise_patterns:
        text = re.sub(pattern, " ", text)

    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _best_name(entity: Dict[str, Any]) -> str:
    return (
        entity.get("name")
        or entity.get("entity_name")
        or entity.get("entity")
        or entity.get("label")
        or ""
    )


def _extract_images_from_entity(entity: Dict[str, Any]) -> List[str]:
    props = entity.get("properties") or {}
    if not isinstance(props, dict):
        props = {}

    candidates = [
        entity.get("image", ""),
        entity.get("mainImage", ""),
        entity.get("images", []),
        entity.get("additionalImages", []),
        props.get("image", ""),
        props.get("mainImage", ""),
        props.get("images", []),
        props.get("additionalImages", []),
        props.get("candidateImage", ""),
    ]

    out: List[str] = []
    seen = set()

    def _flatten(v):
        if v is None:
            return []
        if isinstance(v, list):
            acc = []
            for item in v:
                acc.extend(_flatten(item))
            return acc
        return [v]

    for raw in candidates:
        for item in _flatten(raw):
            s = str(item or "").strip()
            if not s:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(s)

    return out


def _is_valid_image_url(url: str) -> bool:
    low = str(url or "").strip().lower()
    if not low:
        return False
    if not (low.startswith("http://") or low.startswith("https://")):
        return False
    if ".svg" in low:
        return False
    bad_patterns = [
        "_next/static/",
        "_next/image?",
        "/static/media/",
        "logo",
        "icon",
        "sprite",
        "banner",
        "placeholder",
        "favicon",
        "avatar",
        "share",
        "social",
        "financion",
    ]
    if any(p in low for p in bad_patterns):
        return False
    valid_exts = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"]
    return any(ext in low for ext in valid_exts)


def _build_raw_entity_index(all_results: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    index: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for block in all_results:
        url = str(block.get("url") or "").strip()
        for entity in block.get("entities", []) or []:
            if not isinstance(entity, dict):
                continue

            name = _normalize_name_for_merge(_best_name(entity))
            if not url or not name:
                continue

            key = (url, name)
            existing = index.get(key)

            score = float(entity.get("score") or 0)
            if existing is None or score > float(existing.get("score") or 0):
                index[key] = entity

    return index


def _merge_back_enrichment(global_entities: List[Dict[str, Any]], all_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    raw_index = _build_raw_entity_index(all_results)
    merged: List[Dict[str, Any]] = []

    for entity in global_entities:
        if not isinstance(entity, dict):
            merged.append(entity)
            continue

        url = str(entity.get("sourceUrl") or entity.get("url") or "").strip()
        name = _normalize_name_for_merge(_best_name(entity))
        raw = raw_index.get((url, name))

        if not raw:
            merged.append(entity)
            continue

        out = dict(entity)
        props = out.get("properties") or {}
        if not isinstance(props, dict):
            props = {}

        raw_props = raw.get("properties") or {}
        if not isinstance(raw_props, dict):
            raw_props = {}

        # Wikidata
        if not out.get("wikidata_id") and raw.get("wikidata_id"):
            out["wikidata_id"] = raw.get("wikidata_id")
        if not out.get("wikidataId") and raw.get("wikidataId"):
            out["wikidataId"] = raw.get("wikidataId")

        # Coordenadas
        out_coords = out.get("coordinates") or {}
        raw_coords = raw.get("coordinates") or {}
        if not isinstance(out_coords, dict):
            out_coords = {}
        if not isinstance(raw_coords, dict):
            raw_coords = {}

        if out_coords.get("lat") in (None, "") and raw_coords.get("lat") not in (None, ""):
            out_coords["lat"] = raw_coords.get("lat")
        if out_coords.get("lng") in (None, "") and raw_coords.get("lng") not in (None, ""):
            out_coords["lng"] = raw_coords.get("lng")
        if out_coords:
            out["coordinates"] = out_coords

        if out.get("latitude") in (None, "") and raw.get("latitude") not in (None, ""):
            out["latitude"] = raw.get("latitude")
        if out.get("longitude") in (None, "") and raw.get("longitude") not in (None, ""):
            out["longitude"] = raw.get("longitude")

        # Imágenes: conservar solo si son válidas
        candidate_images = _extract_images_from_entity(raw)
        valid_images = [img for img in candidate_images if _is_valid_image_url(img)]
        if valid_images:
            valid_images = valid_images[:3]
            if not out.get("image"):
                out["image"] = valid_images[0]
            if not out.get("mainImage"):
                out["mainImage"] = valid_images[1] if len(valid_images) > 1 else valid_images[0]
            elif out.get("mainImage") == out.get("image") and len(valid_images) > 1:
                out["mainImage"] = valid_images[1]

            existing_images = out.get("images")
            if not isinstance(existing_images, list):
                existing_images = []

            for img in valid_images:
                if img not in existing_images:
                    existing_images.append(img)

            existing_images = existing_images[:3]
            out["images"] = existing_images
            if len(existing_images) > 1:
                out["additionalImages"] = existing_images[1:]

            if not props.get("image"):
                props["image"] = valid_images[0]
            if not props.get("mainImage"):
                props["mainImage"] = valid_images[1] if len(valid_images) > 1 else valid_images[0]
            elif props.get("mainImage") == props.get("image") and len(valid_images) > 1:
                props["mainImage"] = valid_images[1]
            if len(existing_images) > 1 and not props.get("additionalImages"):
                props["additionalImages"] = existing_images[1:]

        # Descripciones largas si se perdieron
        for field in ["description", "short_description", "long_description", "address", "phone", "email"]:
            if not out.get(field) and raw.get(field):
                out[field] = raw.get(field)

        if raw_props:
            merged_props = dict(raw_props)
            merged_props.update(props)
            out["properties"] = merged_props
        else:
            out["properties"] = props

        # Reinyectar metadatos estructurales perdidos durante consolidación/resolución
        for field in [
            "entityId",
            "pageStructure",
            "pageRole",
            "parentEntityId",
            "relationshipType",
            "mentionRole",
            "mentionRelation",
        ]:
            if out.get(field) in (None, "", []):
                raw_value = raw.get(field)
                if raw_value not in (None, "", []):
                    out[field] = raw_value

        if not out.get("sourceUrl") and raw.get("sourceUrl"):
            out["sourceUrl"] = raw.get("sourceUrl")
        if not out.get("url") and raw.get("url"):
            out["url"] = raw.get("url")

        merged.append(out)

    return merged


def _rescue_missing_route_parents(global_entities: List[Dict[str, Any]], all_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rescued = [dict(entity) for entity in global_entities if isinstance(entity, dict)]
    existing_route_pages = {
        str(entity.get("sourceUrl") or entity.get("url") or "").strip()
        for entity in rescued
        if str(entity.get("class") or entity.get("type") or "").strip().lower() == "route"
    }

    for block in all_results:
        page_url = str(block.get("url") or "").strip()
        if not page_url or page_url in existing_route_pages:
            continue

        route_candidates = []
        for raw in block.get("entities", []) or []:
            if not isinstance(raw, dict):
                continue
            raw_type = str(raw.get("class") or raw.get("type") or "").strip().lower()
            if raw_type == "route" or raw.get("_route_parent_seed"):
                route_candidates.append(raw)

        if not route_candidates:
            continue

        route_candidates.sort(
            key=lambda item: (
                float(item.get("score") or 0.0),
                len(str(item.get("name") or item.get("entity_name") or item.get("label") or "")),
            ),
            reverse=True,
        )
        rescued.append(dict(route_candidates[0]))
        existing_route_pages.add(page_url)

    return rescued


def consolidate_entities(all_results, diagnostic=False):
    diag(diagnostic, f"Entrando en consolidate_entities con {len(all_results)} bloques")

    consolidator = EntityDescriptionConsolidator()
    global_entities = consolidator.consolidate(all_results)

    resolver = EntityResolver(
        merge_threshold=0.75,
        weak_variant_threshold=0.92,
        min_name_len_for_direct_match=4,
    )
    global_entities = resolver.deduplicate_entities(global_entities)

    postprocessor = KGPostProcessor()
    global_entities = postprocessor.process(global_entities)

    # Reinyectar enriquecimiento perdido desde resultados crudos
    global_entities = _merge_back_enrichment(global_entities, all_results)
    global_entities = _rescue_missing_route_parents(global_entities, all_results)

    diag(diagnostic, f"Tras postprocess()+merge_back: {len(global_entities)} entidades")
    return global_entities

def predict_from_pages(pages, pipeline, args, diagnostic=False):
    if not pages:
        payload = {
            "status": "ok",
            "mode": "single_url" if args.url else "crawl",
            "start_url": args.start_url,
            "url": args.url,
            "max_pages": args.max_pages,
            "expected_type": getattr(args, "expected_type", None),
            "entity_count": 0,
            "prediction": None,
            "stats": {
                "total_entities": 0,
                "by_type": {},
                "by_type_percent": {},
                "entities_by_type": {},
                "with_wikidata": 0,
                "without_wikidata": 0,
                "with_coordinates": 0,
                "without_coordinates": 0,
                "with_image": 0,
                "without_image": 0,
            },
            "entities": [],
            "message": "No se recuperaron paginas para procesar; revisa start_url, alcance del crawler o conectividad.",
            "page_errors": [],
        }
        return payload, [], []

    all_results, page_errors = process_pages(
        pages=pages,
        pipeline=pipeline,
        args=args,
        diagnostic=diagnostic,
    )

    if not all_results:
        payload = {
            "status": "ok",
            "mode": "single_url" if args.url else "crawl",
            "start_url": args.start_url,
            "url": args.url,
            "max_pages": args.max_pages,
            "expected_type": getattr(args, "expected_type", None),
            "entity_count": 0,
            "prediction": None,
            "stats": {
                "total_entities": 0,
                "by_type": {},
                "by_type_percent": {},
                "entities_by_type": {},
                "with_wikidata": 0,
                "without_wikidata": 0,
                "with_coordinates": 0,
                "without_coordinates": 0,
                "with_image": 0,
                "without_image": 0,
            },
            "entities": [],
            "message": "No se obtuvieron entidades finales válidas; resultado permitido tras filtrado.",
            "page_errors": page_errors,
        }
        return payload, all_results, []

    global_entities = consolidate_entities(all_results, diagnostic=diagnostic)

    global_entities = enforce_closed_world_batch(
        global_entities,
        pipeline.valid_classes,
        ontology_catalog=pipeline.ontology_catalog,
    )

    payload = build_stdout_payload(global_entities, args)

    if page_errors:
        payload["page_errors"] = page_errors

    return payload, all_results, global_entities    


def predict_single_url(url, pipeline, args, diagnostic=False):
    pages = get_pages_for_url(url, max_pages=1, diagnostic=diagnostic)
    payload, all_results, global_entities = predict_from_pages(
        pages=pages,
        pipeline=pipeline,
        args=args,
        diagnostic=diagnostic,
    )
    payload["url"] = url
    payload["mode"] = "single_url"
    return payload, pages, all_results, global_entities


def generate_outputs(global_entities, pipeline, args, pages=None):
    kg_builder = KnowledgeGraphBuilder()
    graph = kg_builder.build_graph(global_entities)
    kg_builder.save_graph(graph, args.kg_output)
    log(f"\n🧠 Knowledge graph guardado en {args.kg_output}")

    if hasattr(kg_builder, "save_html"):
        try:
            kg_builder.save_html(args.kg_html_output)
            log(f"🌐 Visualización HTML guardada en {args.kg_html_output}")
        except Exception as exc:
            log(f"⚠️ No se pudo generar HTML del KG: {exc}")

    reporter = EntitiesReporter(
        getattr(pipeline, "ontology_index", None)
        or getattr(pipeline, "ontology_catalog", {})
    )
    reporter.generate_markdown_report(global_entities, args.report_output)
    log(f"📝 Reporte Markdown generado en {args.report_output}")

    json_exporter = JSONExporter()
    json_exporter.export(global_entities, args.json_output, pages=pages)
    log(f"📦 Export JSON generado en {args.json_output}")

    try:
        graph_visualizer = TourismGraphVisualizer()
        graph_visualizer.build_html(global_entities, args.graph_html_output)
        log(f"🕸️ Visualización de grafo guardada en {args.graph_html_output}")
    except Exception as exc:
        log(f"⚠️ No se pudo generar {args.graph_html_output}: {exc}")

    try:
        map_visualizer = TourismMapVisualizer()
        map_visualizer.build_html(global_entities, args.map_html_output)
        log(f"🗺️ Mapa turístico guardado en {args.map_html_output}")
    except Exception as exc:
        log(f"⚠️ No se pudo generar {args.map_html_output}: {exc}")


def debug_entities(global_entities):
    log("\n=== DEBUG IMAGES ===")
    for e in global_entities[:10]:
        log(
            e.get("name") or e.get("entity_name") or e.get("entity"),
            "image=", e.get("image", ""),
            "mainImage=", e.get("mainImage", ""),
            "props.image=", (e.get("properties", {}) or {}).get("image", ""),
            "props.candidateImage=", (e.get("properties", {}) or {}).get("candidateImage", "")
        )


def main():
    parser = build_parser()
    args = parser.parse_args()

    diagnostic = args.diagnostic or args.benchmark

    if not args.json_stdout:
        log("🚀 Iniciando proyecto de extracción ontológica turística")
        log("ONTOLOGY PATH:", os.path.abspath(args.ontology_path))
        log("EXISTS:", os.path.exists(args.ontology_path))

    diag(diagnostic, f"args={vars(args)}")

    validation_error = validate_inputs(args, diagnostic=diagnostic)
    if validation_error:
        if args.json_stdout:
            safe_json_output(validation_error)
            return
        raise FileNotFoundError(validation_error["message"])

    try:
        pipeline = build_pipeline(args)
        diag(diagnostic, "TourismPipeline inicializado correctamente")

        if args.json_stdout:
            rogue_stdout = StringIO()
            with redirect_stdout(rogue_stdout):
                pages = get_pages(args, diagnostic=diagnostic)
                payload, all_results, global_entities = predict_from_pages(
                    pages=pages,
                    pipeline=pipeline,
                    args=args,
                    diagnostic=diagnostic,
                )

            captured = rogue_stdout.getvalue()
            if captured.strip():
                print(captured, file=sys.stderr, end="")

            json_exporter = JSONExporter()
            payload["entities"] = [
                json_exporter.entity_to_dict(e)
                for e in global_entities
                if isinstance(e, dict)
            ]
            payload["entity_count"] = len(payload["entities"])

            try:
                payload["stats"] = compute_entity_stats(payload["entities"])
            except Exception as e:
                payload["stats"] = {"error": str(e)}

            payload["prediction"] = infer_main_prediction(payload["entities"])

            safe_json_output(payload)

        else:
            pages = get_pages(args, diagnostic=diagnostic)
            log(f"\n📄 Páginas encontradas: {len(pages)}")
            if not pages:
                log("\n⚠️ El crawler no recuperó páginas. No se inicia el procesamiento de entidades.")

            payload, all_results, global_entities = predict_from_pages(
                pages=pages,
                pipeline=pipeline,
                args=args,
                diagnostic=diagnostic,
            )
            
            if payload.get("status") == "error":
                raise RuntimeError(payload.get("message", "Error desconocido en predict_from_pages"))

            if payload.get("entity_count", 0) == 0:
                log("\nℹ️ No se obtuvieron entidades finales válidas en este lote (resultado permitido tras filtrado).")
                return
            
            log(f"\n✅ Total bloques intermedios: {len(all_results)}")
            debug_entities(global_entities)
            generate_outputs(global_entities, pipeline, args, pages=pages)

            log("\n✅ Proceso completado correctamente")

    except Exception as exc:
        error = {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "message": str(exc),
            "url": args.url,
            "start_url": args.start_url,
            "expected_type": getattr(args, "expected_type", None),
        }

        diag(diagnostic, f"EXCEPCIÓN GLOBAL: {repr(exc)}")

        if args.json_stdout:
            safe_json_output(error)
            return

        raise


if __name__ == "__main__":
    main()
