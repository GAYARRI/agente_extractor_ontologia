from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections import Counter


def build_markdown(payload: dict) -> str:
    global_type_counts = Counter()
    for page in payload.get("pages") or []:
        for entity_type, count in (page.get("entityTypeCounts") or {}).items():
            try:
                global_type_counts[entity_type] += int(count)
            except Exception:
                continue

    lines = []
    lines.append("# Conteo de Entidades por Pagina")
    lines.append("")
    lines.append(f"Total de paginas: {payload.get('totalPages', 0)}")
    lines.append(f"Paginas con entidades: {payload.get('pagesWithEntities', 0)}")
    lines.append(f"Paginas sin entidades: {payload.get('pagesWithoutEntities', 0)}")
    lines.append(f"Total de entidades: {payload.get('totalEntities', 0)}")
    lines.append("")
    lines.append("## Resumen de procesamiento")
    lines.append("")
    lines.append(
        f"- Paginas con entidades vs total procesado: "
        f"{payload.get('pagesWithEntities', 0)} / {payload.get('totalPages', 0)}"
    )
    lines.append(
        f"- Cobertura de paginas con entidades: "
        f"{round((payload.get('pagesWithEntities', 0) / max(payload.get('totalPages', 1), 1)) * 100, 2)}%"
    )
    lines.append("")

    if global_type_counts:
        lines.append("## Entidades Totales por Grupo Clasificado")
        lines.append("")
        lines.append("| Grupo | Total |")
        lines.append("| --- | ---: |")
        for entity_type, count in sorted(
            global_type_counts.items(),
            key=lambda item: (-item[1], item[0].lower()),
        ):
            lines.append(f"| {entity_type} | {count} |")
        lines.append("")

    pages_by_entity_count = payload.get("pagesByEntityCount") or {}
    if pages_by_entity_count:
        lines.append("## Resumen global")
        lines.append("")
        for entity_count, page_count in sorted(
            pages_by_entity_count.items(),
            key=lambda item: int(item[0]),
        ):
            lines.append(f"- Paginas con {entity_count} entidades: {page_count}")
        lines.append("")

    for page in payload.get("pages") or []:
        url = str(page.get("url") or "").strip() or "UNKNOWN_PAGE"
        entity_count = page.get("entityCount", 0)
        type_counts = page.get("entityTypeCounts") or {}

        lines.append(f"## {url}")
        lines.append("")
        lines.append(f"- Entidades totales: {entity_count}")
        if type_counts:
            for entity_type, count in sorted(
                type_counts.items(),
                key=lambda item: (-item[1], item[0].lower()),
            ):
                lines.append(f"- {entity_type}: {count}")
        else:
            lines.append("- Sin entidades")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convierte entities_page_counts.json a un reporte Markdown."
    )
    parser.add_argument(
        "input_json",
        nargs="?",
        default="entities_page_counts.json",
        help="Ruta al JSON de conteos por pagina.",
    )
    parser.add_argument(
        "output_md",
        nargs="?",
        default="entities_page_counts.md",
        help="Ruta del Markdown de salida.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_json)
    output_path = Path(args.output_md)

    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    markdown = build_markdown(payload)

    with output_path.open("w", encoding="utf-8") as f:
        f.write(markdown)


if __name__ == "__main__":
    main()
