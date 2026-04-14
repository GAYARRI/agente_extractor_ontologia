from __future__ import annotations

import os
import sys
import json
import argparse
import certifi
import traceback
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from typing import Any, Dict, List

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

    parser.add_argument("--start_url", type=str, default="https://visitasevilla.es/")
    parser.add_argument("--url", type=str, default=None)
    parser.add_argument("--max_pages", type=int, default=2)
    parser.add_argument("--ontology_path", type=str, default="src/ontology/core.rdf")
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
    if not os.path.exists(args.ontology_path):
        error = {
            "status": "error",
            "error_type": "ontology_not_found",
            "message": f"No existe el archivo de ontología: {os.path.abspath(args.ontology_path)}",
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

    for idx, (url, html) in enumerate(pages, start=1):
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


            for i, e in enumerate((result or [])[:3], start=1):
                print(f"     [{i}]")
                print(json.dumps(e, indent=2, ensure_ascii=False))

            print("  -> ENTITIES_JSON:")

            if not result:
                print("     []")
            else:
                for i, e in enumerate(result[:5], start=1):
                    print(f"     [{i}]")
                    print(json.dumps(e, indent=2, ensure_ascii=False))

            # ===============================
            # PRINT ENTIDADES (TOP 5)
            # ===============================
            print("  -> ENTITIES:")

            if not result:
                print("     (no entities)")
            else:
                for i, e in enumerate(result[:5], start=1):
                    if not isinstance(e, dict):
                        print(f"     {i}. {e}")
                        continue

                    name = (
                        e.get("name")
                        or e.get("entity_name")
                        or e.get("entity")
                        or e.get("label")
                        or ""
                    )

                    print(
                        f"     {i}. name={name!r} | "
                        f"type={e.get('type')!r} | "
                        f"semantic_type={e.get('semantic_type')!r} | "
                        f"score={e.get('score')!r}"
                    )  


            diag(diagnostic, f"Tipo de result={type(result).__name__}")

            if result is None:
                raise ValueError("pipeline.run devolvió None")

            if isinstance(result, list):
                if not result:
                    raise ValueError("pipeline.run devolvió lista vacía")

                results_ok.append({
                    "url": url,
                    "entities": result,
                })

            elif isinstance(result, dict):
                # si ya viene en formato bloque
                if "entities" in result and isinstance(result.get("entities"), list):
                    if not result["entities"]:
                        raise ValueError("pipeline.run devolvió dict con entities vacío")
                    block = dict(result)
                    block.setdefault("url", url)
                    results_ok.append(block)
                else:
                    # dict-entity suelta -> envolver
                    results_ok.append({
                        "url": url,
                        "entities": [result],
                    })

            else:
                raise TypeError(f"Tipo de retorno no soportado: {type(result).__name__}")

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

    return results_ok, page_errors


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

    diag(diagnostic, f"Tras postprocess(): {len(global_entities)} entidades")
    return global_entities


def predict_from_pages(pages, pipeline, args, diagnostic=False):
    all_results, page_errors = process_pages(
        pages=pages,
        pipeline=pipeline,
        args=args,
        diagnostic=diagnostic,
    )

    if not all_results:
        message = "No se obtuvo ninguna entidad válida de las páginas procesadas."
        if page_errors:
            first = page_errors[0]
            message = f"{message} Primer error: {first['error_type']}: {first['message']}"

        payload = build_error_payload(
            args,
            message=message,
            error_type="page_processing_error",
            extra={"page_errors": page_errors},
        )
        return payload, all_results, []

    global_entities = consolidate_entities(all_results, diagnostic=diagnostic)
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


def generate_outputs(global_entities, pipeline, args):
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

    reporter = EntitiesReporter(pipeline.ontology_index)
    reporter.generate_markdown_report(global_entities, args.report_output)
    log(f"📝 Reporte Markdown generado en {args.report_output}")

    json_exporter = JSONExporter()
    json_exporter.export(global_entities, args.json_output)
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

            safe_json_output(payload)

        else:
            pages = get_pages(args, diagnostic=diagnostic)
            log(f"\n📄 Páginas encontradas: {len(pages)}")

            payload, all_results, global_entities = predict_from_pages(
                pages=pages,
                pipeline=pipeline,
                args=args,
                diagnostic=diagnostic,
            )

            if payload.get("status") == "error":
                raise RuntimeError(payload.get("message", "Error desconocido en predict_from_pages"))

            log(f"\n✅ Total bloques intermedios: {len(all_results)}")
            debug_entities(global_entities)
            generate_outputs(global_entities, pipeline, args)

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