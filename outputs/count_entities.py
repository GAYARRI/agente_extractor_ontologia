#!/usr/bin/env python3
import json
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re


def has_image(entity: dict) -> bool:
    """
    Considera que una entidad tiene imagen si al menos uno de estos campos
    contiene valor:
      - image
      - mainImage
      - images (lista no vacía)
      - additionalImages (lista no vacía)
    """
    return any([
        bool(entity.get("image")),
        bool(entity.get("mainImage")),
        bool(entity.get("images")),
        bool(entity.get("additionalImages")),
    ])


def has_coordinates(entity: dict) -> bool:
    """
    Considera que una entidad tiene coordenadas si coordinates.lat y
    coordinates.lng existen y no son None.
    """
    coords = entity.get("coordinates") or {}
    lat = coords.get("lat")
    lng = coords.get("lng")
    return lat is not None and lng is not None


def entity_classes(entity: dict) -> list[str]:
    """
    Devuelve las clases de la entidad. Se excluye 'Location' del desglose
    principal porque suele actuar como etiqueta genérica.
    Si una entidad solo tiene 'Location', se mantiene.
    """
    types = entity.get("types") or []
    filtered = [t for t in types if t != "Location"]
    return filtered if filtered else (types or ["SIN_TIPO"])


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
        classes = entity_classes(entity)

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
