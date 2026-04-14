from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Asegura que la raíz del proyecto esté en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from main import build_pipeline, predict_single_url


class BenchmarkArgs:
    def __init__(
        self,
        ontology_path: str,
        max_pages: int,
        use_fewshots: bool = False,
        fewshot_file: str | None = None,
    ):
        self.start_url = "https://visitasevilla.es/"
        self.url = None
        self.max_pages = max_pages
        self.ontology_path = ontology_path
        self.kg_output = "knowledge_graph.ttl"
        self.kg_html_output = "knowledge_graph.html"
        self.report_output = "entities_report.md"
        self.json_output = "entities.json"
        self.graph_html_output = "tourism_graph.html"
        self.map_html_output = "tourism_map.html"
        self.benchmark = True
        self.json_stdout = False
        self.diagnostic = False
        self.use_fewshots = use_fewshots
        self.fewshot_file = fewshot_file
        self.expected_type = None


def debug(msg: str) -> None:
    print(f"[DEBUG] {msg}", file=sys.stderr)


def load_json(path: str | Path) -> Any:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_url_to_type_map(ground_truth: Any) -> Dict[str, str]:
    mapping = {}

    if isinstance(ground_truth, list):
        for item in ground_truth:
            if isinstance(item, dict):
                url = item.get("url")
                typ = item.get("type") or item.get("expected_type")
                if url and typ:
                    mapping[str(url).strip()] = str(typ).strip()

    elif isinstance(ground_truth, dict):
        data = ground_truth.get("data") or ground_truth.get("urls") or []
        for item in data:
            if isinstance(item, dict):
                url = item.get("url")
                typ = item.get("type") or item.get("expected_type")
                if url and typ:
                    mapping[str(url).strip()] = str(typ).strip()

    return mapping


def normalize_ground_truth_urls(ground_truth: Any) -> List[str]:
    urls: List[str] = []

    if isinstance(ground_truth, list):
        for item in ground_truth:
            if isinstance(item, str):
                urls.append(item.strip())
            elif isinstance(item, dict) and "url" in item:
                url = item.get("url")
                if isinstance(url, str) and url.strip():
                    urls.append(url.strip())

    elif isinstance(ground_truth, dict):
        if isinstance(ground_truth.get("urls"), list):
            for item in ground_truth["urls"]:
                if isinstance(item, str):
                    urls.append(item.strip())
                elif isinstance(item, dict) and "url" in item:
                    url = item.get("url")
                    if isinstance(url, str) and url.strip():
                        urls.append(url.strip())

        elif isinstance(ground_truth.get("data"), list):
            for item in ground_truth["data"]:
                if isinstance(item, dict) and "url" in item:
                    url = item.get("url")
                    if isinstance(url, str) and url.strip():
                        urls.append(url.strip())

    seen = set()
    deduped = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            deduped.append(url)

    return deduped


def build_prediction_record(
    url: str,
    result: Dict[str, Any],
    elapsed_seconds: float,
) -> Dict[str, Any]:
    entities = result.get("entities") or []
    return {
        "url": url,
        "status": result.get("status"),
        "prediction": result.get("prediction"),
        "expected_type": result.get("expected_type"),
        "entity_count": result.get("entity_count"),
        "stats": result.get("stats"),
        "entities": entities,
        "top_candidates": entities[:3],
        "elapsed_seconds": round(elapsed_seconds, 3),
        "raw_result": result,
    }


def process_urls(
    urls: List[str],
    url_to_type: Dict[str, str],
    ontology_path: str,
    max_pages: int,
    use_fewshots: bool = False,
    fewshot_file: str | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    predictions: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    bench_args = BenchmarkArgs(
        ontology_path=ontology_path,
        max_pages=max_pages,
        use_fewshots=use_fewshots,
        fewshot_file=fewshot_file,
    )

    debug("Inicializando pipeline una sola vez")
    pipeline = build_pipeline(bench_args)

    total = len(urls)
    print(f"URLs to process: {total}")

    for i, url in enumerate(urls, start=1):
        print(f"[{i}/{total}] Processing: {url}")
        t0 = time.perf_counter()

        try:
            if hasattr(pipeline, "reset_runtime_state"):
                pipeline.reset_runtime_state()

            bench_args.expected_type = url_to_type.get(url)

            result, pages, all_results, global_entities = predict_single_url(
                url=url,
                pipeline=pipeline,
                args=bench_args,
                diagnostic=False,
            )

            elapsed = time.perf_counter() - t0

            if result.get("status") == "error":
                errors.append(
                    {
                        "url": url,
                        "error": result.get("message", "Error devuelto por pipeline"),
                        "elapsed_seconds": round(elapsed, 3),
                        "raw_result": result,
                    }
                )
                print(f"  -> ERROR PIPELINE: {result.get('message', 'sin mensaje')}")
                if result.get("page_errors"):
                    print("  -> PAGE_ERRORS:", json.dumps(result["page_errors"], ensure_ascii=False, indent=2))
                continue

            predictions.append(build_prediction_record(url, result, elapsed))
            print(f"  -> OK ({elapsed:.2f}s)")

        except Exception as e:
            elapsed = time.perf_counter() - t0
            tb = traceback.format_exc()

            errors.append(
                {
                    "url": url,
                    "error": f"{type(e).__name__}: {e}",
                    "elapsed_seconds": round(elapsed, 3),
                    "raw_result": {"traceback": tb},
                }
            )

            print(f"  -> ERROR: {type(e).__name__}: {e}")
            print("----- TRACEBACK BEGIN -----")
            print(tb)
            print("----- TRACEBACK END -----")

    return predictions, errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera predicciones desde benchmark reutilizando una sola instancia del pipeline."
    )

    parser.add_argument("--ground_truth", required=True)
    parser.add_argument("--ontology_path", default="src/ontology/core.rdf")
    parser.add_argument("--output_predictions", default="outputs/predictions_run_001.json")
    parser.add_argument("--output_errors", default="outputs/predictions_errors_run_001.json")
    parser.add_argument("--max_pages", type=int, default=1)
    parser.add_argument("--use_fewshots", action="store_true")
    parser.add_argument("--fewshot_file", type=str, default=None)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ground_truth = load_json(args.ground_truth)
    urls = normalize_ground_truth_urls(ground_truth)
    url_to_type = build_url_to_type_map(ground_truth)

    if not urls:
        raise ValueError("No se encontraron URLs válidas en el ground_truth.")

    predictions, errors = process_urls(
        urls=urls,
        url_to_type=url_to_type,
        ontology_path=args.ontology_path,
        max_pages=args.max_pages,
        use_fewshots=args.use_fewshots,
        fewshot_file=args.fewshot_file,
    )

    save_json(args.output_predictions, predictions)
    save_json(args.output_errors, errors)

    print(f"[DONE] Predicciones guardadas en: {args.output_predictions}")
    print(f"[DONE] Errores guardados en: {args.output_errors}")
    print(f"[DONE] Total predicciones OK: {len(predictions)}")
    print(f"[DONE] Total errores: {len(errors)}")


if __name__ == "__main__":
    main()