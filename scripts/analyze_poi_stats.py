from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: str | Path) -> Any:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def flatten_entities(data: Any) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []

    if not isinstance(data, list):
        return flat

    for item in data:
        if not isinstance(item, dict):
            continue

        entities = item.get("entities", [])
        if isinstance(entities, list):
            for entity in entities:
                if isinstance(entity, dict):
                    merged = dict(entity)
                    if "url" not in merged and item.get("url"):
                        merged["url"] = item.get("url")
                    flat.append(merged)

    return flat


def normalize_type(entity: Dict[str, Any]) -> str:
    cls = entity.get("class")
    if isinstance(cls, str) and cls.strip():
        return cls.strip()

    typ = entity.get("type")
    if isinstance(typ, list) and typ:
        first = str(typ[0]).strip()
        if first:
            return first
    if isinstance(typ, str) and typ.strip():
        return typ.strip()

    return "Unknown"


def has_image(entity: Dict[str, Any]) -> bool:
    if str(entity.get("image", "") or "").strip():
        return True
    if str(entity.get("mainImage", "") or "").strip():
        return True

    images = entity.get("images", [])
    if isinstance(images, list) and any(str(x).strip() for x in images):
        return True

    return False


def has_coordinates(entity: Dict[str, Any]) -> bool:
    coords = entity.get("coordinates") or {}
    if not isinstance(coords, dict):
        return False

    lat = coords.get("lat")
    lng = coords.get("lng")

    return lat not in (None, "") and lng not in (None, "")


def has_wikidata(entity: Dict[str, Any]) -> bool:
    wikidata_id = entity.get("wikidata_id") or entity.get("wikidataId")
    return bool(str(wikidata_id or "").strip())


def has_description(entity: Dict[str, Any]) -> bool:
    for key in ("description", "short_description", "long_description", "shortDescription", "longDescription"):
        value = entity.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def safe_pct(num: int, den: int) -> float:
    if den == 0:
        return 0.0
    return round((num / den) * 100.0, 2)


def analyze_entities(entities: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "total_entities": 0,
        "with_image": 0,
        "without_image": 0,
        "with_coordinates": 0,
        "without_coordinates": 0,
        "with_wikidata": 0,
        "without_wikidata": 0,
        "with_description": 0,
        "without_description": 0,
    }

    by_type = defaultdict(
        lambda: {
            "count": 0,
            "with_image": 0,
            "without_image": 0,
            "with_coordinates": 0,
            "without_coordinates": 0,
            "with_wikidata": 0,
            "without_wikidata": 0,
            "with_description": 0,
            "without_description": 0,
        }
    )

    for entity in entities:
        poi_type = normalize_type(entity)

        img = has_image(entity)
        coords = has_coordinates(entity)
        wikidata = has_wikidata(entity)
        desc = has_description(entity)

        summary["total_entities"] += 1
        by_type[poi_type]["count"] += 1

        if img:
            summary["with_image"] += 1
            by_type[poi_type]["with_image"] += 1
        else:
            summary["without_image"] += 1
            by_type[poi_type]["without_image"] += 1

        if coords:
            summary["with_coordinates"] += 1
            by_type[poi_type]["with_coordinates"] += 1
        else:
            summary["without_coordinates"] += 1
            by_type[poi_type]["without_coordinates"] += 1

        if wikidata:
            summary["with_wikidata"] += 1
            by_type[poi_type]["with_wikidata"] += 1
        else:
            summary["without_wikidata"] += 1
            by_type[poi_type]["without_wikidata"] += 1

        if desc:
            summary["with_description"] += 1
            by_type[poi_type]["with_description"] += 1
        else:
            summary["without_description"] += 1
            by_type[poi_type]["without_description"] += 1

    total = summary["total_entities"]
    summary["pct_with_image"] = safe_pct(summary["with_image"], total)
    summary["pct_with_coordinates"] = safe_pct(summary["with_coordinates"], total)
    summary["pct_with_wikidata"] = safe_pct(summary["with_wikidata"], total)
    summary["pct_with_description"] = safe_pct(summary["with_description"], total)

    by_type_out = {}
    for poi_type, stats in sorted(by_type.items(), key=lambda x: (-x[1]["count"], x[0])):
        count = stats["count"]
        enriched = dict(stats)
        enriched["pct_with_image"] = safe_pct(stats["with_image"], count)
        enriched["pct_with_coordinates"] = safe_pct(stats["with_coordinates"], count)
        enriched["pct_with_wikidata"] = safe_pct(stats["with_wikidata"], count)
        enriched["pct_with_description"] = safe_pct(stats["with_description"], count)
        by_type_out[poi_type] = enriched

    return {
        "summary": summary,
        "by_type": by_type_out,
    }


def print_report(report: Dict[str, Any]) -> None:
    summary = report["summary"]
    by_type = report["by_type"]

    print("\n==============================")
    print("RESUMEN GLOBAL")
    print("==============================")
    print(f"Total entidades:        {summary['total_entities']}")
    print(f"Con imagen:             {summary['with_image']} ({summary['pct_with_image']}%)")
    print(f"Con coordenadas:        {summary['with_coordinates']} ({summary['pct_with_coordinates']}%)")
    print(f"Con Wikidata ID:        {summary['with_wikidata']} ({summary['pct_with_wikidata']}%)")
    print(f"Con descripción:        {summary['with_description']} ({summary['pct_with_description']}%)")

    print("\n==============================")
    print("ESTADÍSTICAS POR TIPO DE POI")
    print("==============================")

    for poi_type, stats in by_type.items():
        print(f"\n[{poi_type}]")
        print(f"  Total:                {stats['count']}")
        print(f"  Con imagen:           {stats['with_image']} ({stats['pct_with_image']}%)")
        print(f"  Con coordenadas:      {stats['with_coordinates']} ({stats['pct_with_coordinates']}%)")
        print(f"  Con Wikidata ID:      {stats['with_wikidata']} ({stats['pct_with_wikidata']}%)")
        print(f"  Con descripción:      {stats['with_description']} ({stats['pct_with_description']}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Estadísticas por tipo de POI")
    parser.add_argument("--input", required=True, help="Ruta al JSON de predicciones")
    parser.add_argument("--output", default="", help="Ruta opcional para guardar el reporte JSON")
    args = parser.parse_args()

    data = load_json(args.input)
    entities = flatten_entities(data)
    report = analyze_entities(entities)
    print_report(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n[DONE] Reporte guardado en: {output_path}")


if __name__ == "__main__":
    main()