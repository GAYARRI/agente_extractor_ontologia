from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlparse


IGNORE_PATTERNS = (
    "elementor_library",
    "wp-json",
    "/aviso-legal",
    "privacidad",
    "cookies",
    "accesibilidad",
    "/feed",
    "/tag/",
    "/category/",
    "/author/",
    "/search/",
)

HIGH_VALUE_SEGMENTS = {
    "area-profesional",
    "ayuntamiento",
    "en",
    "lugar",
    "que-ver-en-pamplona-lugares-imprescindibles",
    "planifica-tu-viaje",
    "tipo-lugar",
}


def load_page_counts(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def split_segments(url: str) -> list[str]:
    path = urlparse(url).path.strip("/")
    return [segment for segment in path.split("/") if segment]


def classify_zero_url(url: str) -> str:
    low = url.lower()
    if any(pattern in low for pattern in IGNORE_PATTERNS):
        return "ignore"
    segments = split_segments(url)
    if not segments:
        return "homepage_or_portal"
    if segments[0] in HIGH_VALUE_SEGMENTS:
        return "likely_rescatable"
    if len(segments) >= 2:
        return "review_by_family"
    return "review_single_segment"


def pattern_key(url: str) -> str:
    parsed = urlparse(url)
    segments = split_segments(url)
    if not segments:
        return "/"
    if "elementor_library" in parsed.query:
        return "?elementor_library"
    if len(segments) == 1:
        return f"/{segments[0]}"
    return f"/{segments[0]}/..."


def priority_score(url: str) -> tuple[int, int]:
    label = classify_zero_url(url)
    weights = {
        "likely_rescatable": 0,
        "review_by_family": 1,
        "review_single_segment": 2,
        "homepage_or_portal": 3,
        "ignore": 4,
    }
    return (weights.get(label, 9), len(split_segments(url)))


def build_report(data: dict, top_n: int = 20) -> str:
    zero_pages = [page for page in data.get("pages", []) if int(page.get("entityCount", 0) or 0) == 0]

    by_pattern: dict[str, list[str]] = defaultdict(list)
    by_label: dict[str, list[str]] = defaultdict(list)
    segment_1 = Counter()
    segment_2 = Counter()

    for page in zero_pages:
        url = str(page.get("url") or "").strip()
        if not url:
            continue
        by_pattern[pattern_key(url)].append(url)
        by_label[classify_zero_url(url)].append(url)
        segments = split_segments(url)
        segment_1[segments[0] if segments else "/"] += 1
        if len(segments) >= 2:
            segment_2[f"{segments[0]}/{segments[1]}"] += 1

    top_rescatable = sorted(
        [url for url in by_label.get("likely_rescatable", [])],
        key=priority_score,
    )[:30]

    lines: list[str] = []
    lines.append("# Analisis de URLs sin entidades")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- Paginas totales procesadas: `{data.get('totalPages', 0)}`")
    lines.append(f"- Paginas sin entidades: `{data.get('pagesWithoutEntities', 0)}`")
    lines.append(f"- Paginas con entidades: `{data.get('pagesWithEntities', 0)}`")
    lines.append("")
    lines.append("## Distribucion por prioridad heuristica")
    lines.append("")
    for label in ("likely_rescatable", "review_by_family", "review_single_segment", "homepage_or_portal", "ignore"):
        lines.append(f"- `{label}`: `{len(by_label.get(label, []))}`")
    lines.append("")
    lines.append("## Patrones de primer segmento mas frecuentes")
    lines.append("")
    lines.append("| Segmento | URLs sin entidades |")
    lines.append("|---|---:|")
    for segment, count in segment_1.most_common(top_n):
        lines.append(f"| `{segment}` | {count} |")
    lines.append("")
    lines.append("## Patrones de dos segmentos mas frecuentes")
    lines.append("")
    lines.append("| Patron | URLs sin entidades |")
    lines.append("|---|---:|")
    for segment, count in segment_2.most_common(top_n):
        lines.append(f"| `{segment}` | {count} |")
    lines.append("")
    lines.append("## Familias de URL mas repetidas")
    lines.append("")
    lines.append("| Patron agrupado | URLs sin entidades | Clasificacion sugerida |")
    lines.append("|---|---:|---|")
    pattern_rows = []
    for pattern, urls in by_pattern.items():
        sample = urls[0]
        pattern_rows.append((len(urls), pattern, classify_zero_url(sample)))
    for count, pattern, label in sorted(pattern_rows, reverse=True)[:top_n]:
        lines.append(f"| `{pattern}` | {count} | `{label}` |")
    lines.append("")
    lines.append("## Muestra prioritaria de URLs probablemente rescatables")
    lines.append("")
    for url in top_rescatable:
        lines.append(f"- {url}")
    lines.append("")
    lines.append("## Muestra de URLs ignorables o de bajo valor")
    lines.append("")
    for url in sorted(by_label.get("ignore", []))[:20]:
        lines.append(f"- {url}")
    lines.append("")
    lines.append("## Siguiente uso recomendado")
    lines.append("")
    lines.append("- Revisar primero las familias `likely_rescatable` con mas volumen.")
    lines.append("- Confirmar con una muestra manual de 5-10 URLs por familia si realmente hay falsos negativos.")
    lines.append("- Convertir cada familia valida en una regla general de rescate, no en excepciones por URL.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analiza las URLs sin entidades agrupandolas por patrones.")
    parser.add_argument("--page-counts", default="entities_page_counts.json")
    parser.add_argument("--output", default="docs/zero_entity_url_patterns.md")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    data = load_page_counts(Path(args.page_counts))
    report = build_report(data, top_n=args.top)
    Path(args.output).write_text(report, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
