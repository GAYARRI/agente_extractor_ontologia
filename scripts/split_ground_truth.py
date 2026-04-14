from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_type(value: Any) -> str:
    if not value:
        return "Unknown"

    if isinstance(value, list):
        if not value:
            return "Unknown"
        value = value[0]

    value = str(value).strip()

    if "#" in value:
        value = value.split("#")[-1]
    elif "/" in value:
        value = value.rstrip("/").split("/")[-1]

    return value or "Unknown"


def infer_destination_from_url(url: str) -> str:
    url = (url or "").lower()

    if "visitasevilla.es" in url:
        return "sevilla"
    if "info.valladolid.es" in url:
        return "valladolid"

    return "unknown"


def get_group_key(record: Dict[str, Any]) -> str:
    url = (record.get("url") or "").strip()
    if url:
        return url
    return f"__missing_url__::{record.get('name', '')}"


def summarize_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_destination = Counter()
    by_type = Counter()
    by_destination_type = Counter()

    for r in records:
        url = r.get("url", "")
        destination = infer_destination_from_url(url)
        entity_type = normalize_type(r.get("types"))

        by_destination[destination] += 1
        by_type[entity_type] += 1
        by_destination_type[f"{destination}::{entity_type}"] += 1

    return {
        "total_records": len(records),
        "by_destination": dict(by_destination),
        "by_type": dict(by_type),
        "by_destination_type": dict(by_destination_type),
    }


def summarize_groups(groups: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    urls_by_destination = Counter()

    for group_key, records in groups.items():
        if records:
            destination = infer_destination_from_url(records[0].get("url", ""))
            urls_by_destination[destination] += 1

    return {
        "total_groups": len(groups),
        "groups_by_destination": dict(urls_by_destination),
    }


def build_group_stats(groups: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, int]]:
    stats = {}

    for group_key, records in groups.items():
        counter = Counter()
        for r in records:
            destination = infer_destination_from_url(r.get("url", ""))
            entity_type = normalize_type(r.get("types"))
            counter[f"dest::{destination}"] += 1
            counter[f"type::{entity_type}"] += 1
            counter[f"combo::{destination}::{entity_type}"] += 1

        stats[group_key] = dict(counter)

    return stats


def stratified_group_split(
    records: List[Dict[str, Any]],
    train_ratio: float = 0.7,
    seed: int = 42,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str], List[str]]:
    random.seed(seed)

    groups = defaultdict(list)
    for r in records:
        groups[get_group_key(r)].append(r)

    group_stats = build_group_stats(groups)
    group_keys = list(groups.keys())
    random.shuffle(group_keys)

    total_records = len(records)
    target_train_records = round(total_records * train_ratio)

    total_combo = Counter()
    for r in records:
        destination = infer_destination_from_url(r.get("url", ""))
        entity_type = normalize_type(r.get("types"))
        total_combo[f"{destination}::{entity_type}"] += 1

    target_train_combo = {
        k: v * train_ratio for k, v in total_combo.items()
    }

    train_keys = []
    val_keys = []

    train_combo = Counter()
    train_count = 0

    def score_if_added(group_key: str) -> float:
        temp_combo = train_combo.copy()
        for k, v in group_stats[group_key].items():
            if k.startswith("combo::"):
                combo_key = k.replace("combo::", "")
                temp_combo[combo_key] += v

        error = 0.0
        for combo_key, target in target_train_combo.items():
            error += abs(temp_combo[combo_key] - target)

        temp_count = train_count + len(groups[group_key])
        error += abs(temp_count - target_train_records) * 0.25

        return error

    for group_key in group_keys:
        if train_count >= target_train_records:
            val_keys.append(group_key)
            continue

        add_score = score_if_added(group_key)

        # score de no añadirlo todavía
        current_error = 0.0
        for combo_key, target in target_train_combo.items():
            current_error += abs(train_combo[combo_key] - target)
        current_error += abs(train_count - target_train_records) * 0.25

        if add_score <= current_error or train_count < target_train_records * 0.85:
            train_keys.append(group_key)
            train_count += len(groups[group_key])

            for k, v in group_stats[group_key].items():
                if k.startswith("combo::"):
                    combo_key = k.replace("combo::", "")
                    train_combo[combo_key] += v
        else:
            val_keys.append(group_key)

    train_records = []
    val_records = []

    for k in train_keys:
        train_records.extend(groups[k])

    for k in val_keys:
        val_records.extend(groups[k])

    return train_records, val_records, train_keys, val_keys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Ruta a ground_truth.json")
    parser.add_argument("--output_dir", default="benchmark/splits", help="Directorio de salida")
    parser.add_argument("--train_ratio", type=float, default=0.7, help="Ratio few-shot/train")
    parser.add_argument("--seed", type=int, default=42, help="Semilla aleatoria")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    records = load_json(input_path)
    if not isinstance(records, list):
        raise TypeError("El JSON de entrada debe ser una lista de registros")

    train_records, val_records, train_keys, val_keys = stratified_group_split(
        records=records,
        train_ratio=args.train_ratio,
        seed=args.seed,
    )

    fewshot_records_path = output_dir / "fewshot_records.json"
    validation_records_path = output_dir / "validation_records.json"
    fewshot_urls_path = output_dir / "fewshot_urls.json"
    validation_urls_path = output_dir / "validation_urls.json"
    report_path = output_dir / "split_report.json"

    save_json(train_records, fewshot_records_path)
    save_json(val_records, validation_records_path)
    save_json(train_keys, fewshot_urls_path)
    save_json(val_keys, validation_urls_path)

    grouped = defaultdict(list)
    for r in records:
        grouped[get_group_key(r)].append(r)

    report = {
        "input_file": str(input_path),
        "train_ratio": args.train_ratio,
        "seed": args.seed,
        "global_summary": summarize_records(records),
        "fewshot_summary": summarize_records(train_records),
        "validation_summary": summarize_records(val_records),
        "global_group_summary": summarize_groups(grouped),
        "fewshot_group_count": len(train_keys),
        "validation_group_count": len(val_keys),
        "fewshot_paths": {
            "records": str(fewshot_records_path),
            "urls": str(fewshot_urls_path),
        },
        "validation_paths": {
            "records": str(validation_records_path),
            "urls": str(validation_urls_path),
        },
    }

    save_json(report, report_path)

    print("[DONE] Split completado")
    print(f"[DONE] Few-shot records: {fewshot_records_path}")
    print(f"[DONE] Validation records: {validation_records_path}")
    print(f"[DONE] Report: {report_path}")
    print()
    print("[SUMMARY] Global:", report["global_summary"])
    print("[SUMMARY] Few-shot:", report["fewshot_summary"])
    print("[SUMMARY] Validation:", report["validation_summary"])


if __name__ == "__main__":
    main()