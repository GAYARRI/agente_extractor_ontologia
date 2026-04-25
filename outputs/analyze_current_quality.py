from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


def entity_class(entity: dict) -> str:
    value = entity.get("class") or entity.get("type") or "Unknown"
    if isinstance(value, list):
        value = value[0] if value else "Unknown"
    return str(value or "Unknown")


def entity_name(entity: dict) -> str:
    return str(
        entity.get("name")
        or entity.get("entity_name")
        or entity.get("entity")
        or entity.get("label")
        or ""
    ).strip()


def entity_url(entity: dict) -> str:
    return str(
        entity.get("sourceUrl")
        or entity.get("url")
        or entity.get("source_url")
        or ""
    ).strip()


def url_family(url: str) -> str:
    low = (url or "").strip().lower()
    if "elementor_library" in low or "wp-json" in low:
        return "technical"
    if any(x in low for x in ("/aviso-legal", "privacidad", "cookies", "accesibilidad")):
        return "legal"
    path = urlparse(low).path.strip("/")
    if not path:
        return "homepage"
    segments = [s for s in path.split("/") if s]
    if len(segments) >= 2 and segments[0] == "en" and segments[1] == "lugar":
        return "en_lugar_detail"
    if segments[0] == "lugar":
        return "lugar_detail"
    if segments[0] == "tipo-lugar":
        return "tipo_lugar"
    if segments[0] == "evento":
        return "evento"
    if segments[0] == "area-profesional":
        return "institutional_programmatic"
    if segments[0] == "ayuntamiento":
        return "ayuntamiento"
    if segments[0] == "planifica-tu-viaje":
        return "planifica"
    if segments[0] in {"blog", "category", "tag"}:
        return "editorial_listing"
    return segments[0]


def classify_zero_page(url: str) -> tuple[str, str]:
    family = url_family(url)
    mapping = {
        "technical": ("correct_empty", "Pagina tecnica o plantilla"),
        "legal": ("correct_empty", "Pagina legal"),
        "homepage": ("review", "Portada o hub principal"),
        "lugar_detail": ("likely_false_negative", "Ficha detalle con alto potencial de entidad"),
        "en_lugar_detail": ("likely_false_negative", "Ficha detalle en ingles con alto potencial"),
        "tipo_lugar": ("expected_empty_if_following_links", "Listado tematico; mejor extraer en fichas enlazadas"),
        "evento": ("expected_empty_if_following_links", "Listado o hub de eventos"),
        "institutional_programmatic": ("likely_false_negative", "Pagina programatica/institucional potencialmente rescatable"),
        "ayuntamiento": ("review", "Pagina mixta institucional/editorial"),
        "planifica": ("review", "Pagina utilitaria o hub de servicios"),
        "editorial_listing": ("correct_empty", "Listado editorial o de categorias"),
    }
    return mapping.get(family, ("review", "Caso frontera"))


def build_unknown_rows(entities: list[dict]) -> list[dict[str, str]]:
    rows = []
    for entity in entities:
        if entity_class(entity).lower() != "unknown":
            continue
        rows.append(
            {
                "name": entity_name(entity),
                "url": entity_url(entity),
                "family": url_family(entity_url(entity)),
                "current_class": "Unknown",
                "probable_class": "",
                "priority": "",
                "notes": "",
            }
        )
    return rows


def build_zero_rows(page_counts: dict, limit: int = 40) -> list[dict[str, str]]:
    pages = page_counts.get("pages", [])
    zero_pages = [page for page in pages if int(page.get("entityCount", 0) or 0) == 0]
    scored = []
    for page in zero_pages:
        url = str(page.get("url") or "").strip()
        label, rationale = classify_zero_page(url)
        family = url_family(url)
        priority = {
            "likely_false_negative": 0,
            "review": 1,
            "expected_empty_if_following_links": 2,
            "correct_empty": 3,
        }.get(label, 9)
        scored.append((priority, family, url, label, rationale))
    scored.sort()
    rows = []
    for idx, (_, family, url, label, rationale) in enumerate(scored[:limit], start=1):
        rows.append(
            {
                "priority": str(idx),
                "url": url,
                "family": family,
                "assessment": label,
                "why": rationale,
                "expected": "",
                "decision": "",
                "notes": "",
            }
        )
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, entities: list[dict], page_counts: dict, unknown_rows: list[dict[str, str]], zero_rows: list[dict[str, str]]) -> None:
    classes = Counter(entity_class(e) for e in entities)
    zero_pages = [page for page in page_counts.get("pages", []) if int(page.get("entityCount", 0) or 0) == 0]
    zero_by_assessment = Counter(classify_zero_page(str(page.get("url") or "").strip())[0] for page in zero_pages)
    lines = [
        "# Revision de calidad actual",
        "",
        "## Resumen",
        "",
        f"- Entidades totales: `{len(entities)}`",
        f"- Unknown actuales: `{len(unknown_rows)}`",
        f"- Paginas sin entidades: `{len(zero_pages)}`",
        "",
        "## Clases principales",
        "",
    ]
    for cls_name, count in classes.most_common(15):
        lines.append(f"- `{cls_name}`: `{count}`")
    lines.extend(
        [
            "",
            "## Paginas sin entidades por evaluacion heuristica",
            "",
        ]
    )
    for label, count in zero_by_assessment.most_common():
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(
        [
            "",
            "## Unknown prioritarios",
            "",
        ]
    )
    for row in unknown_rows[:15]:
        lines.append(f"- `{row['name']}` | `{row['family']}` | {row['url']}")
    lines.extend(
        [
            "",
            "## Paginas vacias a revisar primero",
            "",
        ]
    )
    for row in zero_rows[:20]:
        lines.append(f"- `{row['family']}` | `{row['assessment']}` | {row['url']}")
        lines.append(f"  Motivo: {row['why']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_zero_review_md(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "# Zero Entity Pages Review",
        "",
        "Cada URL va sola en su linea para que el editor la detecte bien.",
        "",
    ]
    for row in rows:
        lines.append(f"## {row['priority']}. {row['family']} | {row['assessment']}")
        lines.append("")
        lines.append(f"URL: {row['url']}")
        lines.append("")
        lines.append(f"Motivo: {row['why']}")
        lines.append("")
        lines.append("Esperado: ")
        lines.append("")
        lines.append("Decision: ")
        lines.append("")
        lines.append("Notas: ")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera artefactos de revision de calidad para entities.json y entities_page_counts.json.")
    parser.add_argument("--entities", default="entities.json")
    parser.add_argument("--page-counts", default="entities_page_counts.json")
    parser.add_argument("--unknown-csv", default="outputs/unknown_entities_review.csv")
    parser.add_argument("--zero-csv", default="outputs/zero_entity_pages_review.csv")
    parser.add_argument("--summary-md", default="docs/current_quality_review.md")
    parser.add_argument("--zero-md", default="docs/zero_entity_pages_review.md")
    args = parser.parse_args()

    entities = json.loads(Path(args.entities).read_text(encoding="utf-8"))
    page_counts = json.loads(Path(args.page_counts).read_text(encoding="utf-8"))

    unknown_rows = build_unknown_rows(entities)
    zero_rows = build_zero_rows(page_counts)

    write_csv(
        Path(args.unknown_csv),
        ["name", "url", "family", "current_class", "probable_class", "priority", "notes"],
        unknown_rows,
    )
    write_csv(
        Path(args.zero_csv),
        ["priority", "url", "family", "assessment", "why", "expected", "decision", "notes"],
        zero_rows,
    )
    write_summary(Path(args.summary_md), entities, page_counts, unknown_rows, zero_rows)
    write_zero_review_md(Path(args.zero_md), zero_rows)

    print(args.unknown_csv)
    print(args.zero_csv)
    print(args.summary_md)
    print(args.zero_md)


if __name__ == "__main__":
    main()
