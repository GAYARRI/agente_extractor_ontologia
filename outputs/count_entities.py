#!/usr/bin/env python3
import json
import argparse
from collections import defaultdict
from pathlib import Path
import re


FORBIDDEN_TYPES = {
    "Thing",
    "Entity",
    "Item",
    "Location",
}

GENERIC_TYPES = {
    "Unknown",
    "Place",
    "Organization",
    "Service",
    "Concept",
    "Accommodation",
}


def has_image(entity: dict) -> bool:
    return any([
        bool(entity.get("image")),
        bool(entity.get("mainImage")),
        bool(entity.get("images")),
        bool(entity.get("additionalImages")),
    ])


def has_coordinates(entity: dict) -> bool:
    coords = entity.get("coordinates") or {}
    lat = coords.get("lat")
    lng = coords.get("lng")
    return lat is not None and lng is not None


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _clean_type(t: str) -> str:
    return str(t).strip()


def _is_valid_type(t: str) -> bool:
    t = _clean_type(t)
    return bool(t) and t not in FORBIDDEN_TYPES


def _sanitize_types(types) -> list[str]:
    out = []
    seen = set()
    for t in _as_list(types):
        t = _clean_type(t)
        if not _is_valid_type(t):
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def entity_primary_class(entity: dict) -> str:
    """
    Devuelve una sola clase principal por entidad, con esta prioridad:
      1. class
      2. primer type válido en types
      3. SIN_TIPO
    """
    entity_class = _clean_type(entity.get("class", ""))
    if _is_valid_type(entity_class):
        return entity_class

    types = _sanitize_types(entity.get("types"))
    if types:
        # Priorizar tipos específicos frente a genéricos
        specific = [t for t in types if t not in GENERIC_TYPES]
        if specific:
            return specific[0]
        return types[0]

    # Compatibilidad por si alguna salida usa "type"
    fallback_type = _sanitize_types(entity.get("type"))
    if fallback_type:
        specific = [t for t in fallback_type if t not in GENERIC_TYPES]
        if specific:
            return specific[0]
        return fallback_type[0]

    return "SIN_TIPO"


def entity_all_classes(entity: dict) -> list[str]:
    """
    Devuelve todas las clases válidas de la entidad para auditoría secundaria,
    excluyendo tipos prohibidos.
    """
    classes = []

    entity_class = _clean_type(entity.get("class", ""))
    if _is_valid_type(entity_class):
        classes.append(entity_class)

    for t in _sanitize_types(entity.get("types")):
        if t not in classes:
            classes.append(t)

    for t in _sanitize_types(entity.get("type")):
        if t not in classes:
            classes.append(t)

    return classes or ["SIN_TIPO"]


def slugify(value: str) -> str:
    value = value.strip().replace("/", "-")
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("_") or "SIN_TIPO"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cuenta entidades, entidades con imagen, con coordenadas y hace desglose por clase."
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default="entities.json",
        help="Ruta al archivo JSON (por defecto: entities.json)",
    )
    parser.add_argument(
        "--export-dir",
        help="Directorio opcional para exportar un JSON por clase de entidad",
    )
    parser.add_argument(
        "--multi-class",
        action="store_true",
        help="Cuenta todas las clases válidas de cada entidad en vez de solo la clase principal",
    )
    args = parser.parse_args()

    json_path = Path(args.json_file)
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Se esperaba que el JSON fuera una lista de entidades.")

    total = len(data)
    total_with_image = sum(1 for e in data if has_image(e))
    total_with_coordinates = sum(1 for e in data if has_coordinates(e))

    stats_by_class = defaultdict(lambda: {
        "total": 0,
        "with_image": 0,
        "with_coordinates": 0,
    })

    entities_by_class = defaultdict(list)

    for entity in data:
        classes = entity_all_classes(entity) if args.multi_class else [entity_primary_class(entity)]

        for cls in classes:
            stats_by_class[cls]["total"] += 1
            if has_image(entity):
                stats_by_class[cls]["with_image"] += 1
            if has_coordinates(entity):
                stats_by_class[cls]["with_coordinates"] += 1

            entities_by_class[cls].append(entity)

    print("=" * 80)
    print("RESUMEN GENERAL")
    print("=" * 80)
    print(f"Entidades detectadas:        {total}")
    print(f"Entidades con imagen:        {total_with_image}")
    print(f"Entidades con coordenadas:   {total_with_coordinates}")
    print()

    print("=" * 80)
    print("DESGLOSE POR CLASE")
    print("=" * 80)
    print(f"{'Clase':35} {'Total':>8} {'Con imagen':>12} {'Con coords':>12}")
    print("-" * 80)

    for cls, stats in sorted(
        stats_by_class.items(),
        key=lambda item: (-item[1]["total"], item[0].lower())
    ):
        print(
            f"{cls:35} "
            f"{stats['total']:>8} "
            f"{stats['with_image']:>12} "
            f"{stats['with_coordinates']:>12}"
        )

    if args.export_dir:
        export_dir = Path(args.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        for cls, entities in entities_by_class.items():
            out_file = export_dir / f"{slugify(cls)}.json"
            with out_file.open("w", encoding="utf-8") as f:
                json.dump(entities, f, ensure_ascii=False, indent=2)

        print()
        print(f"Archivos por clase exportados en: {export_dir.resolve()}")


if __name__ == "__main__":
    main()