from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def entity_name(entity: dict) -> str:
    return str(
        entity.get("name")
        or entity.get("entity_name")
        or entity.get("entity")
        or entity.get("label")
        or ""
    ).strip()


def entity_class(entity: dict) -> str:
    return str(entity.get("class") or entity.get("type") or "Unknown").strip() or "Unknown"


def entity_url(entity: dict) -> str:
    return str(entity.get("sourceUrl") or entity.get("url") or entity.get("source_url") or "").strip()


def classify_noise(entity: dict) -> tuple[str, str]:
    name = normalize(entity_name(entity))
    url = normalize(entity_url(entity))
    cls = normalize(entity_class(entity))

    if cls == "unknown":
        return "unknown", "Entidad sin clasificar"

    if any(token in name for token in ["preguntas", "reserva", "informacion", "información", "como llegar", "localizacion", "ubicacion", "booking", "contacto"]):
        return "ui_or_service_phrase", "Etiqueta operativa o de interfaz"

    if any(token in name for token in ["congreso", "simposio", "jornadas", "convencion", "convención", "asamblea"]) and "/eventos-del-sector" in url:
        if cls == "unknown":
            return "sector_event_unknown", "Evento sectorial sin clase"
        return "sector_event_review", "Evento sectorial potencialmente valido pero revisar"

    if "/area-profesional/" in url and cls in {"garden", "monument", "square", "cathedral", "palace"}:
        return "programmatic_misclassified", "Pagina programatica con clase fisica sospechosa"

    if "/en/lugar/" in url or "/lugar/" in url:
        if cls == "monument" and any(token in name for token in ["guerra", "school", "informacion", "información", "lauren", "jake", "richardson", "hemingway", "barnes"]):
            return "narrative_side_entity", "Entidad narrativa o contextual convertida en monumento"
        if len(name.split()) >= 4 and any(token in name for token in ["descubre", "adentrate", "adéntrate", "narra", "busca"]):
            return "fragment_like_name", "Nombre contaminado por texto narrativo"

    if cls == "monument" and any(token in name for token in ["premio", "union europea", "fundacion", "fundación", "startup", "simposio", "convencion", "convención"]):
        return "monument_inflation", "Clase Monument aplicada a entidad no patrimonial"

    return "", ""


def build_rows(entities: list[dict]) -> list[dict[str, str]]:
    rows = []
    for entity in entities:
        pattern, reason = classify_noise(entity)
        if not pattern:
            continue
        rows.append(
            {
                "pattern": pattern,
                "reason": reason,
                "name": entity_name(entity),
                "class": entity_class(entity),
                "url": entity_url(entity),
                "notes": "",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["pattern", "reason", "name", "class", "url", "notes"], delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, rows: list[dict[str, str]]) -> None:
    counts = Counter(row["pattern"] for row in rows)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["pattern"]].append(row)

    lines = [
        "# Noise Pattern Review",
        "",
        "Resumen de patrones de ruido o mala clasificacion a revisar primero.",
        "",
        "## Patrones",
        "",
    ]
    for pattern, count in counts.most_common():
        lines.append(f"- `{pattern}`: `{count}`")

    for pattern, count in counts.most_common():
        lines.extend(["", f"## {pattern}", ""])
        for row in grouped[pattern][:20]:
            lines.append(f"- `{row['name']}` | `{row['class']}` | {row['url']}")
            lines.append(f"  Motivo: {row['reason']}")

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    entities = json.loads(Path("entities.json").read_text(encoding="utf-8"))
    rows = build_rows(entities)
    write_csv(Path("outputs/noise_pattern_review.csv"), rows)
    write_md(Path("docs/noise_pattern_review.md"), rows)
    print("outputs/noise_pattern_review.csv")
    print("docs/noise_pattern_review.md")


if __name__ == "__main__":
    main()
