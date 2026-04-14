from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from src.ontology.type_normalizer import normalize_type


def load_json_file(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_case_report_csv(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "url",
                "gt_name",
                "gt_type",
                "pred_name",
                "pred_type",
                "match_name",
                "match_type",
                "correct",
                "error_mode",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)    

def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def normalize_url(url):
    if not url:
        return ""
    url = str(url).strip().lower()
    url = url.replace("http://", "https://")
    url = re.sub(r"^https://www\.", "https://", url)
    if "#" in url:
        url = url.split("#")[0]
    url = url.rstrip("/")
    return url


def normalize_type_value(value):
    return normalize_type(value)


def extract_normalized_types(obj):
    raw_types = []

    if not isinstance(obj, dict):
        return []

    if "type" in obj and obj.get("type") is not None:
        type_value = obj.get("type")
        if isinstance(type_value, list):
            raw_types.extend(type_value)
        else:
            raw_types.append(type_value)

    if "types" in obj and obj.get("types") is not None:
        types_value = obj.get("types")
        if isinstance(types_value, list):
            raw_types.extend(types_value)
        else:
            raw_types.append(types_value)

    if "class" in obj and obj.get("class"):
        raw_types.append(obj.get("class"))

    if "normalized_type" in obj and obj.get("normalized_type"):
        raw_types.append(obj.get("normalized_type"))

    normalized = []
    seen = set()

    for t in raw_types:
        t_norm = normalize_type_value(t)
        if t_norm and t_norm not in seen:
            seen.add(t_norm)
            normalized.append(t_norm)

    return normalized


def extract_entity_name(obj):
    if not isinstance(obj, dict):
        return ""

    candidate_fields = [
        "name",
        "entity_name",
        "entity",
        "label",
        "text",
        "title",
        "surface_form",
        "value",
    ]

    for field in candidate_fields:
        value = obj.get(field)
        if isinstance(value, str) and value.strip():
            return normalize_text(value)

    properties = obj.get("properties")
    if isinstance(properties, dict):
        for field in ["label", "name", "title"]:
            value = properties.get(field)
            if isinstance(value, str) and value.strip():
                return normalize_text(value)

    return ""


def gt_case_to_keys(case, match_mode="name_type"):
    name = extract_entity_name(case)
    norm_types = extract_normalized_types(case)

    if match_mode == "name":
        return {(name,)} if name else set()

    if match_mode == "name_type":
        if norm_types:
            return {(name, t) for t in norm_types if name}
        return {(name, "")} if name else set()

    raise ValueError(f"match_mode no soportado: {match_mode}")


def pred_entity_to_keys(entity, match_mode="name_type"):
    name = extract_entity_name(entity)
    norm_types = extract_normalized_types(entity)

    if match_mode == "name":
        return {(name,)} if name else set()

    if match_mode == "name_type":
        if norm_types:
            return {(name, t) for t in norm_types if name}
        return {(name, "")} if name else set()

    raise ValueError(f"match_mode no soportado: {match_mode}")


def compute_metrics(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def build_gt_index(ground_truth, match_mode):
    gt_index = defaultdict(set)

    for case in ground_truth:
        if not isinstance(case, dict):
            continue

        url = normalize_url(case.get("url"))
        if not url:
            continue

        gt_index[url].update(gt_case_to_keys(case, match_mode))

    return dict(gt_index)


def build_pred_index(predictions, match_mode):
    pred_index = {}

    for item in predictions:
        if not isinstance(item, dict):
            continue

        if item.get("status") == "error":
            continue

        url = normalize_url(item.get("url"))
        if not url:
            continue

        entities = item.get("entities", [])
        if not isinstance(entities, list):
            entities = []

        current = set()
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            current.update(pred_entity_to_keys(ent, match_mode))

        pred_index[url] = current

    return pred_index


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )


def normalize_for_match(text):
    if not text:
        return ""
    text = strip_accents(str(text).lower())
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slug_to_text(url: str) -> str:
    url = normalize_url(url)
    if not url:
        return ""

    slug = url.rstrip("/").split("/")[-1]
    slug = slug.replace("-", " ")
    slug = normalize_for_match(slug)
    return slug


def token_overlap_score(a: str, b: str) -> float:
    a_tokens = set(normalize_for_match(a).split())
    b_tokens = set(normalize_for_match(b).split())

    if not a_tokens or not b_tokens:
        return 0.0

    inter = len(a_tokens & b_tokens)
    denom = max(len(a_tokens), len(b_tokens))
    return inter / denom if denom else 0.0


def get_best_text_source(ent: dict) -> str:
    parts = []

    for field in ["description", "short_description", "long_description"]:
        value = ent.get(field)
        if isinstance(value, str) and value.strip():
            parts.append(value)

    props = ent.get("properties")
    if isinstance(props, dict):
        for field in ["description", "label", "title"]:
            value = props.get(field)
            if isinstance(value, str) and value.strip():
                parts.append(value)

    return " | ".join(parts)


def get_entity_rank(ent):
    if not isinstance(ent, dict):
        return -10_000

    name = extract_entity_name(ent)
    if not name:
        return -10_000

    url = ent.get("url", "")
    slug_text = slug_to_text(url)
    types = extract_normalized_types(ent)
    desc_text = normalize_for_match(get_best_text_source(ent))

    quality_score = ent.get("qualityScore", 0) or 0
    score = ent.get("score", 0) or 0
    verisimilitude = ent.get("verisimilitude_score", 0) or 0

    rank = 0.0

    rank += quality_score * 100
    rank += verisimilitude * 20
    rank += score * 10

    overlap = token_overlap_score(name, slug_text)
    rank += overlap * 300

    name_norm = normalize_for_match(name)
    
    normalized_type = ent.get("normalized_type")

    # Penalizar genéricos
    if normalized_type == "place":
        rank -= 80

    # Premiar específicos
    if normalized_type in {
        "monument",
        "event",
        "touristattraction",
        "tourismservice",
        "transportinfrastructure",
        "museum",
        "church",
        "cathedral",
        "square",
        "castle",
        "basilica",
        "culturecenter",
        "exhibitionhall",
        "accommodationestablishment",
        "foodestablishment",
        "route",
    }:
        rank += 40

    quality_decision = normalize_text(ent.get("qualityDecision"))
    if quality_decision and quality_decision != "keep":
        rank -= 100

    wikidata_id = ent.get("wikidata_id") or ent.get("wikidataId")
    if isinstance(wikidata_id, str) and wikidata_id.strip():
        rank += 20

    return rank


def build_pred_index_top1(predictions, match_mode):
    pred_index = {}

    for item in predictions:
        if not isinstance(item, dict):
            continue

        if item.get("status") == "error":
            continue

        url = normalize_url(item.get("url"))
        if not url:
            continue

        entities = item.get("entities", [])
        if not isinstance(entities, list) or not entities:
            pred_index[url] = set()
            continue

        valid_entities = [
            e for e in entities
            if isinstance(e, dict) and extract_entity_name(e)
        ]
        if not valid_entities:
            pred_index[url] = set()
            continue

        ranked = sorted(valid_entities, key=get_entity_rank, reverse=True)
        best_entity = ranked[0]

        print(
            f"[TOP1] {url}\n"
            f"  -> {extract_entity_name(best_entity)} | "
            f"{extract_normalized_types(best_entity)} | "
            f"rank={get_entity_rank(best_entity):.2f}"
        )

        pred_index[url] = pred_entity_to_keys(best_entity, match_mode)

    return pred_index


def evaluate_urls(gt_index, pred_index):
    rows = []

    for url in sorted(gt_index.keys()):
        gt_set = gt_index.get(url, set())
        pred_set = pred_index.get(url, set())

        tp_set = gt_set & pred_set
        fp_set = pred_set - gt_set
        fn_set = gt_set - pred_set

        metrics = compute_metrics(len(tp_set), len(fp_set), len(fn_set))

        rows.append({
            "url": url,
            "num_gt_cases": len(gt_set),
            "num_pred_cases": len(pred_set),
            "metrics": metrics,
            "tp_items": [list(x) for x in sorted(tp_set)],
            "fp_items": [list(x) for x in sorted(fp_set)],
            "fn_items": [list(x) for x in sorted(fn_set)],
        })

    rows.sort(key=lambda x: (x["metrics"]["f1"], x["metrics"]["recall"], x["url"]))
    return rows


def evaluate_global(per_url):
    tp = sum(r["metrics"]["tp"] for r in per_url)
    fp = sum(r["metrics"]["fp"] for r in per_url)
    fn = sum(r["metrics"]["fn"] for r in per_url)
    return compute_metrics(tp, fp, fn)


def evaluate_by_type(ground_truth, predictions):
    gt_by_type = defaultdict(set)
    pred_by_type = defaultdict(set)

    for case in ground_truth:
        if not isinstance(case, dict):
            continue

        url = normalize_url(case.get("url"))
        name = extract_entity_name(case)

        if not url or not name:
            continue

        for t in extract_normalized_types(case):
            gt_by_type[t].add((url, name))

    for item in predictions:
        if not isinstance(item, dict):
            continue

        if item.get("status") == "error":
            continue

        url = normalize_url(item.get("url"))
        entities = item.get("entities", [])

        if not url or not isinstance(entities, list):
            continue

        for ent in entities:
            if not isinstance(ent, dict):
                continue

            name = extract_entity_name(ent)
            if not name:
                continue

            for t in extract_normalized_types(ent):
                pred_by_type[t].add((url, name))

    all_types = sorted(set(gt_by_type.keys()) | set(pred_by_type.keys()))
    result = {}

    for t in all_types:
        gt_set = gt_by_type.get(t, set())
        pred_set = pred_by_type.get(t, set())

        result[t] = compute_metrics(
            len(gt_set & pred_set),
            len(pred_set - gt_set),
            len(gt_set - pred_set),
        )

    return result


def evaluate_case_by_case(ground_truth, pred_index_top1):
    rows = []

    for case in ground_truth:
        if not isinstance(case, dict):
            continue

        url = normalize_url(case.get("url"))
        if not url:
            continue

        gt_name = extract_entity_name(case)
        gt_types = extract_normalized_types(case)
        gt_type = gt_types[0] if gt_types else ""

        pred_keys = pred_index_top1.get(url, set())

        if pred_keys:
            pred_name, pred_type = list(pred_keys)[0]
        else:
            pred_name, pred_type = "", ""

        match_name = (gt_name == pred_name)
        match_type = (gt_type == pred_type)

        if not pred_name:
            error_mode = "NO_PRED"
        elif match_name and match_type:
            error_mode = "OK"
        elif match_name and not match_type:
            error_mode = "TYPE_ONLY"
        elif not match_name and match_type:
            error_mode = "NAME_ONLY_UNLIKELY"
        else:
            error_mode = "BOTH"

        rows.append({
            "url": url,
            "gt_name": gt_name,
            "gt_type": gt_type,
            "pred_name": pred_name,
            "pred_type": pred_type,
            "match_name": match_name,
            "match_type": match_type,
            "correct": match_name and match_type,
            "error_mode": error_mode,
        })

    return rows


def print_summary(total_cases, total_urls, pred_urls, global_metrics, by_type, per_url):
    print("\n" + "=" * 70)
    print("RESUMEN DEL BENCHMARK")
    print("=" * 70)
    print(f"URLs únicas en ground truth: {total_urls}")
    print(f"Casos totales en ground truth: {total_cases}")
    print(f"URLs con predicción: {pred_urls}")

    print("\n" + "=" * 70)
    print("MÉTRICAS GLOBALES")
    print("=" * 70)
    print(f"TP:        {global_metrics['tp']}")
    print(f"FP:        {global_metrics['fp']}")
    print(f"FN:        {global_metrics['fn']}")
    print(f"Precision: {global_metrics['precision']:.6f}")
    print(f"Recall:    {global_metrics['recall']:.6f}")
    print(f"F1:        {global_metrics['f1']:.6f}")

    print("\n" + "=" * 70)
    print("MÉTRICAS POR TIPO")
    print("=" * 70)
    for etype, m in by_type.items():
        print(
            f"{etype:25} TP={m['tp']:4d} FP={m['fp']:4d} FN={m['fn']:4d} "
            f"P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f}"
        )

    print("\n" + "=" * 70)
    print("PEORES URLs")
    print("=" * 70)
    for row in per_url[:10]:
        m = row["metrics"]
        print(
            f"{row['url']}\n"
            f"  GT={row['num_gt_cases']} PRED={row['num_pred_cases']} "
            f"TP={m['tp']} FP={m['fp']} FN={m['fn']} "
            f"P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f}"
        )


def main():
    print("USANDO evaluate.py DESDE:", __file__)
    print("MARCA VERSION EVALUATOR: clean_v3_type_normalizer")

    parser = argparse.ArgumentParser()
    parser.add_argument("--ground_truth", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", default="outputs/evaluation_report.json")
    parser.add_argument("--match_mode", choices=["name", "name_type"], default="name_type")
    args = parser.parse_args()

    ground_truth = load_json_file(args.ground_truth)
    predictions = load_json_file(args.predictions)

    if not isinstance(ground_truth, list):
        raise ValueError("ground_truth debe ser una lista")
    if not isinstance(predictions, list):
        raise ValueError("predictions debe ser una lista")

    print("\nDEBUG GT TYPES")
    for case in ground_truth[:3]:
        print(
            case.get("name"),
            case.get("types"),
            extract_normalized_types(case),
            gt_case_to_keys(case, args.match_mode)
        )

    print("\nDEBUG PRED TYPES")
    shown = 0
    for item in predictions:
        if isinstance(item, dict) and isinstance(item.get("entities"), list):
            print("URL:", item.get("url"))
            for ent in item["entities"][:5]:
                print(
                    "raw_entity =", ent,
                    "\n  extracted_name =", extract_entity_name(ent),
                    "\n  extracted_types =", extract_normalized_types(ent),
                    "\n  keys =", pred_entity_to_keys(ent, args.match_mode),
                )
            shown += 1
            if shown >= 2:
                break

    gt_index = build_gt_index(ground_truth, args.match_mode)
    pred_index = build_pred_index(predictions, args.match_mode)
    pred_index_top1 = build_pred_index_top1(predictions, args.match_mode)

    per_url = evaluate_urls(gt_index, pred_index)
    global_metrics = evaluate_global(per_url)
    by_type = evaluate_by_type(ground_truth, predictions)

    per_url_top1 = evaluate_urls(gt_index, pred_index_top1)
    global_metrics_top1 = evaluate_global(per_url_top1)

    case_rows = evaluate_case_by_case(ground_truth, pred_index_top1)
    save_case_report_csv("outputs/case_by_case_top1.csv", case_rows)
    print("\n[DONE] Case-by-case guardado en outputs/case_by_case_top1.csv")

    report = {
        "config": {
            "ground_truth": args.ground_truth,
            "predictions": args.predictions,
            "match_mode": args.match_mode,
        },
        "dataset_summary": {
            "total_ground_truth_cases": len(ground_truth),
            "total_ground_truth_urls": len(gt_index),
            "total_prediction_urls": len(pred_index),
            "total_prediction_urls_top1": len(pred_index_top1),
        },
        "summary": global_metrics,
        "summary_top1": global_metrics_top1,
        "by_type": by_type,
        "per_url": per_url,
        "per_url_top1": per_url_top1,
        "case_by_case_top1_csv": "outputs/case_by_case_top1.csv",
    }

    save_json(args.output, report)

    print_summary(
        len(ground_truth),
        len(gt_index),
        len(pred_index),
        global_metrics,
        by_type,
        per_url
    )

    print("\n" + "=" * 70)
    print(f"MÉTRICAS TOP-1 POR URL ({args.match_mode})")
    print("=" * 70)
    print(f"TP:        {global_metrics_top1['tp']}")
    print(f"FP:        {global_metrics_top1['fp']}")
    print(f"FN:        {global_metrics_top1['fn']}")
    print(f"Precision: {global_metrics_top1['precision']:.6f}")
    print(f"Recall:    {global_metrics_top1['recall']:.6f}")
    print(f"F1:        {global_metrics_top1['f1']:.6f}")

    print(f"\n[DONE] Reporte guardado en: {args.output}")


if __name__ == "__main__":
    main()