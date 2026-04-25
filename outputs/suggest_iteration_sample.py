from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


LOW_SIGNAL_TYPES = {
    "Unknown",
    "Location",
    "Place",
    "Thing",
    "Entity",
    "Item",
    "Concept",
    "ConceptScheme",
}

LISTING_HINTS = (
    "/category/",
    "/blog/",
    "/page/",
    "/evento/",
    "/eventos/",
    "/tipo-lugar/",
    "/que-ver",
    "/que-hacer",
    "/donde-",
)

INSTITUTIONAL_HINTS = (
    "area-profesional",
    "estrateg",
    "plan",
    "municipal",
    "ayuntamiento",
    "pstd",
    "sf365",
)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def classify_page_family(url: str) -> str:
    low = (url or "").lower()
    if any(token in low for token in INSTITUTIONAL_HINTS):
        return "institucional"
    if "/evento/" in low or "/eventos/" in low:
        return "evento"
    if any(token in low for token in LISTING_HINTS):
        return "listado"
    return "detalle"


def summarize_entities_by_url(entities: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for entity in entities or []:
        if not isinstance(entity, dict):
            continue
        url = str(entity.get("url") or entity.get("sourceUrl") or "").strip()
        if not url:
            continue
        grouped[url].append(entity)
    return grouped


def entity_type(entity: dict) -> str:
    cls = str(entity.get("class") or "").strip()
    if cls:
        return cls
    types = entity.get("types") or []
    if isinstance(types, list) and types:
        return str(types[0]).strip() or "Unknown"
    return "Unknown"


def pick_candidates(entities_by_url: dict[str, list[dict]], page_counts: dict, limit_per_group: int = 5) -> list[dict]:
    candidates = []
    pages = page_counts.get("pages") or []

    pages_without_entities = []
    low_signal = []
    institutional = []
    multi_entity = []

    for page in pages:
        if not isinstance(page, dict):
            continue

        url = str(page.get("url") or "").strip()
        count = int(page.get("entityCount", 0) or 0)
        family = classify_page_family(url)
        entities = entities_by_url.get(url, [])
        types = sorted({entity_type(e) for e in entities if isinstance(e, dict)})

        if count == 0:
            pages_without_entities.append(
                {
                    "url": url,
                    "family": family,
                    "expected": "",
                    "actual": "0 entidades",
                    "error_type": "falso negativo potencial",
                    "notes": "Revisar si la pagina deberia producir entidades o ignorarse.",
                }
            )
            continue

        if count >= 2:
            multi_entity.append(
                {
                    "url": url,
                    "family": family,
                    "expected": "",
                    "actual": f"{count} entidades | clases: {', '.join(types)}",
                    "error_type": "revisar posible duplicado o exceso",
                    "notes": "Confirmar si el numero de entidades es correcto para esta pagina.",
                }
            )

        if any(t in LOW_SIGNAL_TYPES for t in types):
            low_signal.append(
                {
                    "url": url,
                    "family": family,
                    "expected": "",
                    "actual": f"{count} entidades | clases: {', '.join(types)}",
                    "error_type": "mal clasificado potencial",
                    "notes": "La pagina tiene tipos genericos o de baja señal.",
                }
            )

        if family == "institucional":
            institutional.append(
                {
                    "url": url,
                    "family": family,
                    "expected": "",
                    "actual": f"{count} entidades | clases: {', '.join(types)}",
                    "error_type": "caso institucional a validar",
                    "notes": "Comprobar si deberia producir PublicService, TourismOrganisation, Promotion, etc.",
                }
            )

    for bucket in [pages_without_entities, low_signal, institutional, multi_entity]:
        candidates.extend(bucket[:limit_per_group])

    deduped = []
    seen = set()
    for item in candidates:
        url = item["url"]
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(item)
    return deduped


def build_markdown(candidates: list[dict]) -> str:
    lines = []
    lines.append("# Borrador de Muestra para Iteracion")
    lines.append("")
    lines.append("Este borrador se ha generado automaticamente a partir de `entities.json` y `entities_page_counts.json`.")
    lines.append("Completa manualmente las columnas `Esperado` y ajusta `Tipo de error` si hace falta.")
    lines.append("")
    lines.append("| ID | URL | Familia de pagina | Esperado | Actual | Tipo de error | Notas |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")

    for idx, item in enumerate(candidates, start=1):
        lines.append(
            f"| {idx} | {item['url']} | {item['family']} | {item['expected']} | "
            f"{item['actual']} | {item['error_type']} | {item['notes']} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sugiere una muestra inicial para una iteracion de mejora."
    )
    parser.add_argument("--entities", default="entities.json", help="Ruta a entities.json")
    parser.add_argument("--page-counts", default="entities_page_counts.json", help="Ruta a entities_page_counts.json")
    parser.add_argument(
        "--output",
        default="docs/iteration_sample_autodraft.md",
        help="Ruta del markdown de salida",
    )
    parser.add_argument(
        "--limit-per-group",
        type=int,
        default=5,
        help="Numero maximo de candidatos por grupo heuristico",
    )
    args = parser.parse_args()

    entities = load_json(Path(args.entities))
    page_counts = load_json(Path(args.page_counts))

    entities_by_url = summarize_entities_by_url(entities)
    candidates = pick_candidates(
        entities_by_url=entities_by_url,
        page_counts=page_counts,
        limit_per_group=args.limit_per_group,
    )

    markdown = build_markdown(candidates)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    print(f"Candidatos generados: {len(candidates)}")
    print(f"Salida: {output_path}")


if __name__ == "__main__":
    main()
