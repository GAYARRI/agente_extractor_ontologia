from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: str | Path) -> Any:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_records(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]

    if isinstance(data, dict):
        for key in ("data", "items", "results", "documents", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        return [data]

    return []


def get_best_classname_from_mtd(record: Dict[str, Any]) -> Dict[str, Any]:
    mtd = record.get("mtd", {}) or {}
    if not isinstance(mtd, dict):
        return {"classname": "Unknown", "score": None}

    ontology_data = mtd.get("ontology_data", {}) or {}
    if not isinstance(ontology_data, dict):
        return {"classname": "Unknown", "score": None}

    classes = ontology_data.get("classes", [])
    if not isinstance(classes, list) or not classes:
        return {"classname": "Unknown", "score": None}

    valid = []
    for item in classes:
        if not isinstance(item, dict):
            continue

        classname = item.get("classname")
        score = item.get("score")

        if not classname:
            continue

        try:
            score = float(score)
        except (TypeError, ValueError):
            continue

        valid.append({
            "classname": str(classname).strip(),
            "score": score,
        })

    if not valid:
        return {"classname": "Unknown", "score": None}

    best = max(valid, key=lambda x: x["score"])
    return best


def analyze(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    classname_counter = Counter()
    rows = []

    for idx, rec in enumerate(records, start=1):
        best = get_best_classname_from_mtd(rec)
        classname = best["classname"]
        score = best["score"]

        classname_counter[classname] += 1

        rows.append({
            "record_index": idx,
            "tracking_id": rec.get("tracking_id"),
            "url": ((rec.get("firecrawl") or {}).get("url") if isinstance(rec.get("firecrawl"), dict) else None),
            "best_classname": classname,
            "best_score": score,
        })

    total = len(records)
    distribution = []
    for classname, count in classname_counter.most_common():
        pct = round((count / total) * 100, 2) if total else 0.0
        distribution.append({
            "classname": classname,
            "count": count,
            "percent": pct,
        })

    return {
        "summary": {
            "total_records": total,
            "unique_classnames": len(classname_counter),
        },
        "distribution": distribution,
        "rows": rows,
    }


def print_report(report: Dict[str, Any]) -> None:
    summary = report["summary"]
    distribution = report["distribution"]

    print("\n==============================")
    print("RESUMEN")
    print("==============================")
    print(f"Total registros:         {summary['total_records']}")
    print(f"Classnames únicas:       {summary['unique_classnames']}")

    print("\n==============================")
    print("CONTEO POR CLASSNAME MÁXIMA")
    print("==============================")
    for item in distribution:
        print(
            f"{item['classname']}: "
            f"{item['count']} "
            f"({item['percent']}%)"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cuenta registros por classname con score máximo dentro de mtd.ontology_data.classes"
    )
    parser.add_argument("--input", required=True, help="Ruta al fichero JSON de entrada")
    parser.add_argument(
        "--output",
        default="outputs/mtd_max_classname_count.json",
        help="Ruta al fichero JSON de salida",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    data = load_json(args.input)
    records = normalize_records(data)

    if not records:
        raise ValueError("No se encontraron registros válidos en el JSON.")

    report = analyze(records)
    save_json(args.output, report)
    print_report(report)

    print(f"\n[DONE] Reporte guardado en: {args.output}")


if __name__ == "__main__":
    main()