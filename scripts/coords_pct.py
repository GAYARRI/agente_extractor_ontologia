from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXCLUDED_TYPES = {"Event", "Route", "Unknown"}


def short_type(entity: dict[str, Any]) -> str:
    raw = str((entity.get("class") or entity.get("type") or "Unknown")).strip()
    return raw.split("#")[-1].split("/")[-1] or "Unknown"


def has_coordinates(entity: dict[str, Any]) -> bool:
    coords = entity.get("coordinates") or {}
    return isinstance(coords, dict) and coords.get("lat") is not None and coords.get("lng") is not None


def load_entities(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("entities", [])
    return [item for item in items if isinstance(item, dict)]


def compute_stats(path: Path) -> dict[str, Any]:
    items = load_entities(path)
    physical = [item for item in items if short_type(item) not in EXCLUDED_TYPES]
    with_coords = sum(1 for item in physical if has_coordinates(item))
    total = len(physical)

    return {
        "file": str(path),
        "entity_total": len(items),
        "physical_total": total,
        "with_coordinates": with_coords,
        "without_coordinates": total - with_coords,
        "percentage": round((with_coords / total * 100) if total else 0.0, 2),
        "criterion": "physical = all except Event, Route, Unknown",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick percentage of physical entities with coordinates")
    parser.add_argument("json_file", nargs="?", default="entities.json", help="Path to entities JSON file")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    path = Path(args.json_file)
    result = compute_stats(path)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"File: {result['file']}")
    print(f"Physical entities: {result['physical_total']}")
    print(f"With coordinates: {result['with_coordinates']}")
    print(f"Without coordinates: {result['without_coordinates']}")
    print(f"Percentage: {result['percentage']}%")


if __name__ == "__main__":
    main()
