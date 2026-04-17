#!/usr/bin/env python3
import json
import argparse
from collections import defaultdict, Counter
from pathlib import Path
import re
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
    "Accommodation",
}

# Normalize common variants into canonical labels.
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
}

# Higher score = better candidate for primary class.
TYPE_PRIORITY = {
    "Hotel": 100,
    "Restaurant": 100,
    "Museum": 100,
    "Airport": 100,
    "Bar": 95,
    "Cafe": 95,
    "TouristAttraction": 90,
    "Accommodation": 40,
    "Service": 20,
    "Organization": 10,
    "Place": 5,
    "Concept": 0,
    "Unknown": 0,
}

# Minimal class-specific completeness expectations.
EXPECTED_FIELDS = {
    "Hotel": ["name", "coordinates"],
    "Restaurant": ["name", "coordinates"],
    "Museum": ["name"],
    "Airport": ["name", "coordinates"],
    "Bar": ["name", "coordinates"],
    "Cafe": ["name", "coordinates"],
    "TouristAttraction": ["name"],
}


def has_image(entity: Dict[str, Any]) -> bool:
    return any([
        bool(entity.get("image")),
        bool(entity.get("mainImage")),
        bool(entity.get("images")),
        bool(entity.get("additionalImages")),
    ])


def has_coordinates(entity: Dict[str, Any]) -> bool:
    coords = entity.get("coordinates") or {}
    lat = coords.get("lat")
    lng = coords.get("lng")
    return lat is not None and lng is not None


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clean_type(t: Any) -> str:
    raw = _normalize_spaces(str(t))
    if not raw:
        return ""
    canonical = CANONICAL_TYPE_MAP.get(raw.lower())
    return canonical or raw


def _is_valid_type(t: str) -> bool:
    t = _clean_type(t)
    return bool(t) and t not in FORBIDDEN_TYPES


def _sanitize_types(types: Any) -> List[str]:
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


def class_quality(label: str) -> str:
    if label == "SIN_TIPO":
        return "missing"
    if label in GENERIC_TYPES:
        return "generic"
    return "specific"


def iter_class_candidates(entity: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    """
    Yield (source, class_label) candidates from class/types/type fields.
    """
    for source, values in [
        ("class", entity.get("class")),
        ("types", entity.get("types")),
        ("type", entity.get("type")),
    ]:
        for t in _sanitize_types(values):
            yield source, t


def entity_primary_class(entity: Dict[str, Any]) -> str:
    """
    Pick the best primary class using:
      - canonicalization
      - forbidden filtering
      - specificity scoring
      - slight preference for 'class' source, without letting generic labels always win
    """
    candidates = []
    for source, label in iter_class_candidates(entity):
        score = TYPE_PRIORITY.get(label, 50)

        # Prefer specific over generic.
        if label not in GENERIC_TYPES:
            score += 15

        # Slight source bias only.
        if source == "class":
            score += 5
        elif source == "types":
            score += 2

        candidates.append((score, label))

    if not candidates:
        return "SIN_TIPO"

    candidates.sort(key=lambda x: (-x[0], x[1].lower()))
    return candidates[0][1]


def entity_all_classes(entity: Dict[str, Any]) -> List[str]:
    classes = []
    seen = set()

    for _, label in iter_class_candidates(entity):
        if label not in seen:
            seen.add(label)
            classes.append(label)

    return classes or ["SIN_TIPO"]


def entity_specific_classes(entity: Dict[str, Any]) -> List[str]:
    return [c for c in entity_all_classes(entity) if c not in GENERIC_TYPES and c != "SIN_TIPO"]


def entity_declared_class(entity: Dict[str, Any]) -> str:
    c = _clean_type(entity.get("class", ""))
    return c if _is_valid_type(c) else ""


def has_class_conflict(entity: Dict[str, Any]) -> bool:
    declared = entity_declared_class(entity)
    if not declared:
        return False

    specific = entity_specific_classes(entity)
    if not specific:
        return False

    return declared not in specific


def normalize_text(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def entity_key(entity: Dict[str, Any]) -> str:
    """
    Stable-ish dedupe key:
      1. explicit id / externalId / url if present
      2. name + rounded coordinates
      3. fallback name only
    """
    ext_id = entity.get("id") or entity.get("externalId") or entity.get("url")
    if ext_id:
        return "id|" + normalize_text(ext_id)

    name = normalize_text(entity.get("name"))
    coords = entity.get("coordinates") or {}
    lat = coords.get("lat")
    lng = coords.get("lng")

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
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field)
    return missing


def slugify(value: str) -> str:
    value = value.strip().replace("/", "-")
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("_") or "SIN_TIPO"


def print_section(title: str) -> None:
    print("=" * 100)
    print(title)
    print("=" * 100)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audita entidades: deduplicación, clases primarias más precisas, "
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
        help="Cuenta todas las clases válidas por entidad en vez de solo la clase principal (solo auditoría secundaria)",
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

    # Dedupe analysis
    key_counts = Counter(entity_key(e) for e in data)
    duplicate_groups = {k: c for k, c in key_counts.items() if c > 1}
    total_unique_entities = len(key_counts)
    duplicate_entities = sum(c - 1 for c in key_counts.values() if c > 1)

    # High-level quality metrics
    primary_quality_counter = Counter()
    conflict_count = 0
    ambiguous_count = 0
    low_completeness_count = 0

    ambiguous_pair_counter = Counter()

    stats_by_class = defaultdict(lambda: {
        "total": 0,
        "with_image": 0,
        "with_coordinates": 0,
        "generic_primary": 0,
        "missing_expected_fields": 0,
    })

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
            if class_quality(primary) == "generic":
                stats_by_class[cls]["generic_primary"] += 1
            if missing_expected:
                stats_by_class[cls]["missing_expected_fields"] += 1

            entities_by_class[cls].append(entity)

    # Duplicate candidate export bucket
    if duplicate_groups:
        seen = set()
        dup_entities = []
        for entity in data:
            k = entity_key(entity)
            if key_counts[k] > 1 and id(entity) not in seen:
                dup_entities.append(entity)
                seen.add(id(entity))
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
        key=lambda item: (-item[1]["total"], item[0].lower())
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

        # Per-class exports
        per_class_dir = export_dir / "by_class"
        per_class_dir.mkdir(parents=True, exist_ok=True)

        for cls, entities in entities_by_class.items():
            out_file = per_class_dir / f"{slugify(cls)}.json"
            with out_file.open("w", encoding="utf-8") as f:
                json.dump(entities, f, ensure_ascii=False, indent=2)

        # Audit-focused exports
        audit_dir = export_dir / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        for bucket, entities in audit_buckets.items():
            out_file = audit_dir / f"{slugify(bucket)}.json"
            with out_file.open("w", encoding="utf-8") as f:
                json.dump(entities, f, ensure_ascii=False, indent=2)

        # Summary export
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