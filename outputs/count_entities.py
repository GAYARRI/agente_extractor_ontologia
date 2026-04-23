#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


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
    "ConceptScheme",
    "Accommodation",
    "SIN_TIPO",
}

# Normalización de variantes frecuentes
CANONICAL_TYPE_MAP = {
    "hotel": "Hotel",
    "hotels": "Hotel",
    "lodging": "Accommodation",
    "accommodation": "Accommodation",
    "restaurant": "Restaurant",
    "restaurants": "Restaurant",
    "museum": "Museum",
    "museums": "Museum",
    "airport": "Airport",
    "airports": "Airport",
    "bar": "Bar",
    "bars": "Bar",
    "cafe": "Cafe",
    "cafes": "Cafe",
    "coffee shop": "Cafe",
    "tourist attraction": "TouristAttraction",
    "touristattraction": "TouristAttraction",
    "attraction": "TouristAttraction",
    "townhall": "TownHall",
    "town hall": "TownHall",
    "cathedral": "Cathedral",
    "church": "Church",
    "palace": "Palace",
    "castle": "Castle",
    "route": "Route",
    "event": "Event",
    "garden": "Garden",
    "park": "Park",
    "monument": "Monument",
}

# Cuanto mayor, más preferible como clase primaria
TYPE_PRIORITY = {
    "TownHall": 120,
    "Cathedral": 120,
    "Church": 115,
    "Palace": 115,
    "Castle": 115,
    "Museum": 110,
    "Route": 110,
    "Event": 110,
    "Park": 105,
    "Garden": 105,
    "Monument": 100,
    "Hotel": 100,
    "Restaurant": 100,
    "Airport": 100,
    "Bar": 95,
    "Cafe": 95,
    "TouristAttraction": 90,
    "Accommodation": 40,
    "Service": 20,
    "Organization": 10,
    "Place": 5,
    "ConceptScheme": 0,
    "Concept": 0,
    "Unknown": 0,
    "SIN_TIPO": 0,
}

# Campos esperados mínimos por clase
EXPECTED_FIELDS = {
    "TownHall": ["name"],
    "Cathedral": ["name"],
    "Church": ["name"],
    "Palace": ["name"],
    "Castle": ["name"],
    "Museum": ["name"],
    "Route": ["name"],
    "Event": ["name"],
    "Park": ["name"],
    "Garden": ["name"],
    "Monument": ["name"],
    "Hotel": ["name", "coordinates"],
    "Restaurant": ["name", "coordinates"],
    "Airport": ["name", "coordinates"],
    "Bar": ["name", "coordinates"],
    "Cafe": ["name", "coordinates"],
    "TouristAttraction": ["name"],
}


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _local_name(value: Any) -> str:
    text = _normalize_spaces(value)
    if not text:
        return ""
    if "#" in text:
        text = text.split("#")[-1]
    if "/" in text:
        text = text.rstrip("/").split("/")[-1]
    return _normalize_spaces(text)


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _clean_type(value: Any) -> str:
    raw = _local_name(value)
    if not raw:
        return ""
    return CANONICAL_TYPE_MAP.get(raw.lower(), raw)


def _is_valid_type(label: str) -> bool:
    label = _clean_type(label)
    return bool(label) and label not in FORBIDDEN_TYPES


def _sanitize_types(types: Any) -> List[str]:
    out: List[str] = []
    seen = set()

    for value in _as_list(types):
        label = _clean_type(value)
        if not _is_valid_type(label):
            continue
        if label in seen:
            continue
        seen.add(label)
        out.append(label)

    return out


def has_image(entity: Dict[str, Any]) -> bool:
    images = entity.get("images")
    additional_images = entity.get("additionalImages") or entity.get("additional_images")
    return any(
        [
            bool(entity.get("image")),
            bool(entity.get("mainImage") or entity.get("main_image")),
            bool(images),
            bool(additional_images),
        ]
    )


def has_coordinates(entity: Dict[str, Any]) -> bool:
    coords = entity.get("coordinates") or {}
    lat = coords.get("lat")
    lng = coords.get("lng")

    if lat is None:
        lat = entity.get("latitude")
    if lng is None:
        lng = entity.get("longitude")

    return lat is not None and lng is not None


def class_quality(label: str) -> str:
    if not label or label == "SIN_TIPO":
        return "missing"
    if label in GENERIC_TYPES:
        return "generic"
    return "specific"


def iter_class_candidates(entity: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    """
    Devuelve pares (origen, etiqueta_clase) a partir de class/types/type y variantes.
    """
    fields = [
        ("class", entity.get("class")),
        ("types", entity.get("types")),
        ("type", entity.get("type")),
        ("class_raw", entity.get("class_raw")),
        ("types_raw", entity.get("types_raw")),
        ("typesRaw", entity.get("typesRaw")),
    ]

    for source, values in fields:
        for label in _sanitize_types(values):
            yield source, label


def entity_primary_class(entity: Dict[str, Any]) -> str:
    candidates: List[Tuple[int, str]] = []

    for source, label in iter_class_candidates(entity):
        score = TYPE_PRIORITY.get(label, 50)

        if label not in GENERIC_TYPES:
            score += 15

        if source == "class":
            score += 5
        elif source == "types":
            score += 2
        elif source == "type":
            score += 1

        candidates.append((score, label))

    if not candidates:
        return "SIN_TIPO"

    candidates.sort(key=lambda x: (-x[0], x[1].lower()))
    return candidates[0][1]


def entity_all_classes(entity: Dict[str, Any]) -> List[str]:
    classes: List[str] = []
    seen = set()

    for _, label in iter_class_candidates(entity):
        if label not in seen:
            seen.add(label)
            classes.append(label)

    return classes or ["SIN_TIPO"]


def entity_specific_classes(entity: Dict[str, Any]) -> List[str]:
    return [c for c in entity_all_classes(entity) if c not in GENERIC_TYPES and c != "SIN_TIPO"]


def entity_declared_class(entity: Dict[str, Any]) -> str:
    label = _clean_type(entity.get("class"))
    return label if _is_valid_type(label) else ""


def has_class_conflict(entity: Dict[str, Any]) -> bool:
    declared = entity_declared_class(entity)
    if not declared:
        return False

    specific = entity_specific_classes(entity)
    if not specific:
        return False

    return declared not in specific


def entity_key(entity: Dict[str, Any]) -> str:
    """
    Clave estable de deduplicación:
      1. id/externalId/url/sourceUrl
      2. nombre + coordenadas redondeadas
      3. nombre
    """
    ext_id = (
        entity.get("id")
        or entity.get("externalId")
        or entity.get("external_id")
        or entity.get("url")
        or entity.get("sourceUrl")
    )
    if ext_id:
        return "id|" + normalize_text(ext_id)

    name = normalize_text(entity.get("name") or entity.get("entity_name") or entity.get("label"))
    coords = entity.get("coordinates") or {}
    lat = coords.get("lat", entity.get("latitude"))
    lng = coords.get("lng", entity.get("longitude"))

    if lat is not None and lng is not None:
        try:
            return f"namecoords|{name}|{round(float(lat), 4)}|{round(float(lng), 4)}"
        except (ValueError, TypeError):
            pass

    return "name|" + name


def entity_missing_expected_fields(entity: Dict[str, Any], primary_class: str) -> List[str]:
    missing = []

    for field in EXPECTED_FIELDS.get(primary_class, []):
        if field == "coordinates":
            if not has_coordinates(entity):
                missing.append(field)
        else:
            value = entity.get(field)
            if value is None:
                missing.append(field)
            elif isinstance(value, str) and not value.strip():
                missing.append(field)

    return missing


def slugify(value: str) -> str:
    value = str(value or "").strip().replace("/", "-")
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("_") or "SIN_TIPO"


def print_section(title: str) -> None:
    print("=" * 100)
    print(title)
    print("=" * 100)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audita entidades: deduplicación, clases primarias precisas, "
            "conflictos class/types, ambigüedad y calidad por clase."
        )
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        default="entities.json",
        help="Ruta al archivo JSON (por defecto: entities.json)",
    )
    parser.add_argument(
        "--export-dir",
        help="Directorio opcional para exportar JSONs de auditoría",
    )
    parser.add_argument(
        "--multi-class",
        action="store_true",
        help="Cuenta todas las clases válidas por entidad en vez de solo la primaria",
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

    key_counts = Counter(entity_key(e) for e in data)
    duplicate_groups = {k: c for k, c in key_counts.items() if c > 1}
    total_unique_entities = len(key_counts)
    duplicate_entities = sum(c - 1 for c in key_counts.values() if c > 1)

    primary_quality_counter = Counter()
    conflict_count = 0
    ambiguous_count = 0
    low_completeness_count = 0

    ambiguous_pair_counter = Counter()

    stats_by_class = defaultdict(
        lambda: {
            "total": 0,
            "with_image": 0,
            "with_coordinates": 0,
            "generic_primary": 0,
            "missing_expected_fields": 0,
        }
    )

    entities_by_class = defaultdict(list)
    audit_buckets = defaultdict(list)

    for entity in data:
        primary = entity_primary_class(entity)
        primary_quality = class_quality(primary)
        primary_quality_counter[primary_quality] += 1

        specific = entity_specific_classes(entity)
        if len(specific) >= 2:
            ambiguous_count += 1
            pair = tuple(sorted(specific[:2]))
            ambiguous_pair_counter[pair] += 1
            audit_buckets["ambiguous_entities"].append(entity)

        if has_class_conflict(entity):
            conflict_count += 1
            audit_buckets["class_conflicts"].append(entity)

        missing_expected = entity_missing_expected_fields(entity, primary)
        if missing_expected:
            low_completeness_count += 1

        if primary_quality == "missing":
            audit_buckets["missing_type"].append(entity)
        elif primary_quality == "generic":
            audit_buckets["generic_only"].append(entity)

        classes = entity_all_classes(entity) if args.multi_class else [primary]

        for cls in classes:
            stats_by_class[cls]["total"] += 1
            if has_image(entity):
                stats_by_class[cls]["with_image"] += 1
            if has_coordinates(entity):
                stats_by_class[cls]["with_coordinates"] += 1
            if primary_quality == "generic":
                stats_by_class[cls]["generic_primary"] += 1
            if missing_expected:
                stats_by_class[cls]["missing_expected_fields"] += 1

            entities_by_class[cls].append(entity)

    if duplicate_groups:
        seen = set()
        dup_entities = []
        for entity in data:
            k = entity_key(entity)
            marker = (k, id(entity))
            if key_counts[k] > 1 and marker not in seen:
                dup_entities.append(entity)
                seen.add(marker)
        audit_buckets["duplicate_candidates"] = dup_entities

    print_section("RESUMEN GENERAL")
    print(f"Entidades detectadas (raw):                {total}")
    print(f"Entidades únicas estimadas:                {total_unique_entities}")
    print(f"Duplicados estimados:                      {duplicate_entities}")
    print(f"Grupos duplicados:                         {len(duplicate_groups)}")
    print(f"Entidades con imagen:                      {total_with_image}")
    print(f"Entidades con coordenadas:                 {total_with_coordinates}")
    print()

    print_section("CALIDAD DE CLASIFICACIÓN")
    print(f"Clase primaria específica:                 {primary_quality_counter['specific']}")
    print(f"Clase primaria genérica:                   {primary_quality_counter['generic']}")
    print(f"Clase primaria ausente (SIN_TIPO):         {primary_quality_counter['missing']}")
    print(f"Conflictos entre class y types:            {conflict_count}")
    print(f"Entidades ambiguas (>=2 clases específicas): {ambiguous_count}")
    print(f"Entidades con campos esperados incompletos: {low_completeness_count}")
    print()

    print_section("DESGLOSE POR CLASE")
    print(
        f"{'Clase':30} {'Total':>8} {'Img':>8} {'Coords':>8} "
        f"{'Prim.gen':>10} {'Faltan campos':>15}"
    )
    print("-" * 100)

    for cls, stats in sorted(
        stats_by_class.items(),
        key=lambda item: (-item[1]["total"], item[0].lower()),
    ):
        print(
            f"{cls:30} "
            f"{stats['total']:>8} "
            f"{stats['with_image']:>8} "
            f"{stats['with_coordinates']:>8} "
            f"{stats['generic_primary']:>10} "
            f"{stats['missing_expected_fields']:>15}"
        )

    if ambiguous_pair_counter:
        print()
        print_section("PARES DE CLASES MÁS AMBIGUOS")
        print(f"{'Par de clases':50} {'Casos':>8}")
        print("-" * 100)
        for pair, count in ambiguous_pair_counter.most_common(10):
            print(f"{' / '.join(pair):50} {count:>8}")

    if args.export_dir:
        export_dir = Path(args.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        per_class_dir = export_dir / "by_class"
        per_class_dir.mkdir(parents=True, exist_ok=True)

        for cls, entities in entities_by_class.items():
            out_file = per_class_dir / f"{slugify(cls)}.json"
            with out_file.open("w", encoding="utf-8") as f:
                json.dump(entities, f, ensure_ascii=False, indent=2)

        audit_dir = export_dir / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        for bucket, entities in audit_buckets.items():
            out_file = audit_dir / f"{slugify(bucket)}.json"
            with out_file.open("w", encoding="utf-8") as f:
                json.dump(entities, f, ensure_ascii=False, indent=2)

        summary = {
            "total_raw_entities": total,
            "total_unique_entities_estimated": total_unique_entities,
            "duplicate_entities_estimated": duplicate_entities,
            "duplicate_groups": len(duplicate_groups),
            "with_image": total_with_image,
            "with_coordinates": total_with_coordinates,
            "primary_class_quality": dict(primary_quality_counter),
            "class_conflicts": conflict_count,
            "ambiguous_entities": ambiguous_count,
            "entities_with_missing_expected_fields": low_completeness_count,
            "top_ambiguous_pairs": [
                {"pair": list(pair), "count": count}
                for pair, count in ambiguous_pair_counter.most_common(20)
            ],
            "stats_by_class": dict(stats_by_class),
        }

        with (export_dir / "summary.json").open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print()
        print(f"Export de auditoría generado en: {export_dir.resolve()}")


if __name__ == "__main__":
    main()
