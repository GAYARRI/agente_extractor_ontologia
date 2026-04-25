from __future__ import annotations

import argparse
import contextlib
import io
import os
from pathlib import Path
import sys

import certifi
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from src.tourism_pipeline_ontology_driven import TourismPipeline


DEFAULT_URLS = [
    "https://visitpamplonairuna.com/lugar/archivo-real-y-general-de-navarra",
    "https://visitpamplonairuna.com/lugar/catedral-de-santa-maria-la-real",
    "https://visitpamplonairuna.com/lugar/espacio-sanfermin-espazioa",
    "https://visitpamplonairuna.com/en/lugar/belena-de-portalapea",
    "https://visitpamplonairuna.com/en/lugar/pump-track",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Traza etapas del pipeline para un conjunto pequeno de URLs.")
    parser.add_argument("--ontology-path", default="src/ontology/core.rdf")
    parser.add_argument("--output", default="docs/pipeline_trace_report.md")
    parser.add_argument("--url", action="append", dest="urls", help="URL a trazar; se puede repetir.")
    return parser.parse_args()


def build_pipeline(ontology_path: str) -> TourismPipeline:
    pipeline = TourismPipeline(
        ontology_path=ontology_path,
        llm=None,
        use_fewshots=False,
        benchmark_mode=False,
        debug=True,
    )
    # El objetivo es diagnosticar caidas del pipeline sin depender del LLM externo.
    pipeline.llm_supervisor = None
    return pipeline


def run_case(pipeline: TourismPipeline, url: str) -> dict[str, str]:
    stderr_buffer = io.StringIO()
    stdout_buffer = io.StringIO()
    entities = []
    error = ""

    try:
        with contextlib.redirect_stderr(stderr_buffer), contextlib.redirect_stdout(stdout_buffer):
            entities = pipeline.run("", url=url) or []
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    return {
        "url": url,
        "stdout": stdout_buffer.getvalue(),
        "stderr": stderr_buffer.getvalue(),
        "entity_count": str(len(entities or [])),
        "entities": "\n".join(
            f"- {item.get('name')!r} | class={item.get('class')!r} | type={item.get('type')!r}"
            for item in entities
            if isinstance(item, dict)
        ),
        "error": error,
    }


def write_report(path: str, rows: list[dict[str, str]]) -> None:
    lines = [
        "# Pipeline Trace Report",
        "",
        "Trazas de diagnostico por URL.",
        "",
    ]
    for row in rows:
        lines.append(f"## {row['url']}")
        lines.append("")
        lines.append(f"- Entidades finales: `{row['entity_count']}`")
        if row["error"]:
            lines.append(f"- Error: `{row['error']}`")
        lines.append("")
        lines.append("### Entidades")
        lines.append("")
        lines.append(row["entities"] or "_Sin entidades finales_")
        lines.append("")
        lines.append("### Stderr")
        lines.append("")
        lines.append("```text")
        lines.append((row["stderr"] or "").strip())
        lines.append("```")
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    os.environ["SSL_CERT_FILE"] = certifi.where()
    urls = args.urls or DEFAULT_URLS
    pipeline = build_pipeline(args.ontology_path)
    rows = [run_case(pipeline, url) for url in urls]
    write_report(args.output, rows)
    print(args.output)


if __name__ == "__main__":
    main()
