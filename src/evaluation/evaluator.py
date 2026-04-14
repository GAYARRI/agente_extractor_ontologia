from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ontology_distance import OntologyDistance
from src.ontology_taxonomy import ONTOLOGY_PARENT_MAP
from src.evaluation.type_normalizer import normalize_type_name


SOFT_THRESHOLD = 0.75


@dataclass
class EvalPair:
    url: str
    gt_name: str
    gt_type: str
    pred_name: str
    pred_type: str
    exact_name_match: bool
    exact_type_match: bool
    exact_match: bool
    name_similarity: float
    class_distance: Optional[int]
    class_similarity: float
    global_similarity: float
    prediction_rank: Optional[int]


class Evaluator:
    def __init__(
        self,
        name_weight: float = 0.35,
        class_weight: float = 0.65,
    ) -> None:
        self.name_weight = name_weight
        self.class_weight = class_weight
        self.dist_engine = OntologyDistance(ONTOLOGY_PARENT_MAP)

    # =========================================================
    # IO
    # =========================================================

    def load_json(self, path: str | Path) -> Any:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"No existe el archivo: {path}")
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_json(self, path: str | Path, data: Any) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # =========================================================
    # Normalización
    # =========================================================

    def normalize_text(self, text: Any) -> str:
        text = "" if text is None else str(text)
        text = text.lower().strip()
        text = re.sub(r"[^\wáéíóúñü\s]", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def normalize_class_name(self, value: Any) -> str:
        if not value:
            return ""

        if isinstance(value, list):
            value = value[0] if value else ""

        value = str(value).strip()

        if "#" in value:
            value = value.split("#")[-1]
        elif "/" in value:
            value = value.rstrip("/").split("/")[-1]

        return value.strip()

    def compute_name_similarity(self, a: str, b: str) -> float:
        a_norm = self.normalize_text(a)
        b_norm = self.normalize_text(b)

        if not a_norm or not b_norm:
            return 0.0

        return round(SequenceMatcher(None, a_norm, b_norm).ratio(), 6)

    # =========================================================
    # Ground truth
    # =========================================================

    def extract_gt_name(self, item: Dict[str, Any]) -> str:
        candidates = [
            item.get("name"),
            item.get("entity_name"),
            item.get("entity"),
            item.get("label"),
            item.get("title"),
        ]
        for c in candidates:
            if isinstance(c, str) and c.strip():
                return c.strip()

        if isinstance(item.get("case"), list) and item["case"]:
            if len(item["case"]) >= 1 and isinstance(item["case"][0], str):
                return item["case"][0].strip()

        return ""

    def extract_gt_type(self, item: Dict[str, Any]) -> str:
        candidates = [
            item.get("type"),
            item.get("class"),
            item.get("expected_type"),
            item.get("expected_class"),
        ]
        for c in candidates:
            norm = self.normalize_class_name(c)
            if norm:
                return norm

        if isinstance(item.get("types"), list) and item["types"]:
            return self.normalize_class_name(item["types"][0])

        if isinstance(item.get("case"), list) and len(item["case"]) >= 2:
            return self.normalize_class_name(item["case"][1])

        return ""

    def normalize_ground_truth(self, ground_truth: Any) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []

        if isinstance(ground_truth, dict):
            if isinstance(ground_truth.get("data"), list):
                ground_truth = ground_truth["data"]
            elif isinstance(ground_truth.get("cases"), list):
                ground_truth = ground_truth["cases"]
            elif isinstance(ground_truth.get("ground_truth"), list):
                ground_truth = ground_truth["ground_truth"]

        if not isinstance(ground_truth, list):
            return items

        for item in ground_truth:
            if not isinstance(item, dict):
                continue

            url = str(item.get("url", "")).strip()
            name = self.extract_gt_name(item)
            gt_type = self.extract_gt_type(item)

            if not url or not name or not gt_type:
                continue

            gt_type = normalize_type_name(gt_type)

            items.append({
                "url": url,
                "name": name,
                "type": gt_type,
            })

        return items

    # =========================================================
    # Predicciones
    # =========================================================

    def extract_pred_name(self, item: Dict[str, Any]) -> str:
        candidates = [
            item.get("name"),
            item.get("entity_name"),
            item.get("entity"),
            item.get("label"),
            item.get("title"),
        ]
        for c in candidates:
            if isinstance(c, str) and c.strip():
                return c.strip()
        return ""

    def extract_pred_type(self, item: Dict[str, Any]) -> str:
        candidates = [
            item.get("class"),
            item.get("type"),
            item.get("prediction"),
        ]
        for c in candidates:
            norm = self.normalize_class_name(c)
            if norm:
                return norm

        if isinstance(item.get("types"), list) and item["types"]:
            return self.normalize_class_name(item["types"][0])

        return ""

    def flatten_predictions(self, predictions: Any) -> List[Dict[str, Any]]:
        flat: List[Dict[str, Any]] = []

        if not isinstance(predictions, list):
            return flat

        for url_record in predictions:
            if not isinstance(url_record, dict):
                continue

            url = str(url_record.get("url", "")).strip()
            if not url:
                continue

            entities = url_record.get("entities")

            if isinstance(entities, list):
                for rank, entity in enumerate(entities, start=1):
                    if not isinstance(entity, dict):
                        continue

                    name = self.extract_pred_name(entity)
                    pred_type = self.extract_pred_type(entity)

                    if not name and not pred_type:
                        continue

                    pred_type = normalize_type_name(pred_type)

                    flat.append({
                        "url": url,
                        "name": name,
                        "type": pred_type,
                        "rank": rank,
                        "raw": entity,
                    })
                continue

            name = self.extract_pred_name(url_record)
            pred_type = self.extract_pred_type(url_record)

            if name or pred_type:
                pred_type = normalize_type_name(pred_type)
                flat.append({
                    "url": url,
                    "name": name,
                    "type": pred_type,
                    "rank": 1,
                    "raw": url_record,
                })

        return flat

    # =========================================================
    # Matching
    # =========================================================

    def build_eval_pair(
        self,
        gt_item: Dict[str, str],
        pred_item: Dict[str, Any],
    ) -> EvalPair:
        gt_name = gt_item["name"]
        gt_type = normalize_type_name(gt_item["type"])
        pred_name = pred_item.get("name", "")
        pred_type = normalize_type_name(pred_item.get("type", ""))

        exact_name_match = self.normalize_text(gt_name) == self.normalize_text(pred_name)
        exact_type_match = gt_type == pred_type
        exact_match = exact_name_match and exact_type_match

        name_similarity = self.compute_name_similarity(gt_name, pred_name)
        class_distance = self.dist_engine.shortest_taxonomic_distance(gt_type, pred_type)
        class_similarity = round(self.dist_engine.similarity(gt_type, pred_type), 6)

        global_similarity = round(
            self.name_weight * name_similarity + self.class_weight * class_similarity,
            6,
        )

        return EvalPair(
            url=gt_item["url"],
            gt_name=gt_name,
            gt_type=gt_type,
            pred_name=pred_name,
            pred_type=pred_type,
            exact_name_match=exact_name_match,
            exact_type_match=exact_type_match,
            exact_match=exact_match,
            name_similarity=name_similarity,
            class_distance=class_distance,
            class_similarity=class_similarity,
            global_similarity=global_similarity,
            prediction_rank=pred_item.get("rank"),
        )

    def best_prediction_for_gt(
        self,
        gt_item: Dict[str, str],
        url_predictions: List[Dict[str, Any]],
    ) -> Optional[EvalPair]:
        if not url_predictions:
            return None

        scored_pairs = [self.build_eval_pair(gt_item, pred) for pred in url_predictions]

        scored_pairs.sort(
            key=lambda x: (
                x.global_similarity,
                x.class_similarity,
                x.name_similarity,
                -(x.prediction_rank or 9999),
            ),
            reverse=True,
        )

        return scored_pairs[0]

    # =========================================================
    # Métricas
    # =========================================================

    def safe_mean(self, values: List[float]) -> float:
        if not values:
            return 0.0
        return round(sum(values) / len(values), 6)

    def compute_summary(self, pairs: List[EvalPair]) -> Dict[str, Any]:
        if not pairs:
            return {
                "total_cases": 0,
                "exact_match_accuracy": 0.0,
                "exact_type_accuracy": 0.0,
                "accuracy_at_1": 0.0,
                "accuracy_at_2": 0.0,
                "soft_accuracy": 0.0,
                "mean_class_distance": None,
                "mean_class_similarity": 0.0,
                "mean_name_similarity": 0.0,
                "mean_global_similarity": 0.0,
            }

        exact_match_accuracy = self.safe_mean([1.0 if p.exact_match else 0.0 for p in pairs])
        exact_type_accuracy = self.safe_mean([1.0 if p.exact_type_match else 0.0 for p in pairs])

        accuracy_at_1 = self.safe_mean([
            1.0 if p.class_distance is not None and p.class_distance <= 1 else 0.0
            for p in pairs
        ])
        accuracy_at_2 = self.safe_mean([
            1.0 if p.class_distance is not None and p.class_distance <= 2 else 0.0
            for p in pairs
        ])

        soft_accuracy = self.safe_mean([
            1.0 if p.global_similarity >= SOFT_THRESHOLD else 0.0
            for p in pairs
        ])

        class_distances = [float(p.class_distance) for p in pairs if p.class_distance is not None]
        mean_class_distance = round(sum(class_distances) / len(class_distances), 6) if class_distances else None

        mean_class_similarity = self.safe_mean([p.class_similarity for p in pairs])
        mean_name_similarity = self.safe_mean([p.name_similarity for p in pairs])
        mean_global_similarity = self.safe_mean([p.global_similarity for p in pairs])

        return {
            "total_cases": len(pairs),
            "exact_match_accuracy": exact_match_accuracy,
            "exact_type_accuracy": exact_type_accuracy,
            "accuracy_at_1": accuracy_at_1,
            "accuracy_at_2": accuracy_at_2,
            "soft_accuracy": soft_accuracy,
            "mean_class_distance": mean_class_distance,
            "mean_class_similarity": mean_class_similarity,
            "mean_name_similarity": mean_name_similarity,
            "mean_global_similarity": mean_global_similarity,
        }

    def compute_by_gt_type(self, pairs: List[EvalPair]) -> Dict[str, Any]:
        groups: Dict[str, List[EvalPair]] = {}

        for p in pairs:
            groups.setdefault(p.gt_type, []).append(p)

        out: Dict[str, Any] = {}
        for gt_type, group in groups.items():
            out[gt_type] = self.compute_summary(group)

        return out

    # =========================================================
    # API pública
    # =========================================================

    def evaluate(
        self,
        ground_truth_path: str | Path,
        predictions_path: str | Path,
    ) -> Dict[str, Any]:
        ground_truth_raw = self.load_json(ground_truth_path)
        predictions_raw = self.load_json(predictions_path)

        gt_items = self.normalize_ground_truth(ground_truth_raw)
        pred_items = self.flatten_predictions(predictions_raw)

        pred_by_url: Dict[str, List[Dict[str, Any]]] = {}
        for pred in pred_items:
            pred_by_url.setdefault(pred["url"], []).append(pred)

        best_pairs: List[EvalPair] = []
        unmatched_gt: List[Dict[str, Any]] = []

        for gt_item in gt_items:
            url_predictions = pred_by_url.get(gt_item["url"], [])
            best_pair = self.best_prediction_for_gt(gt_item, url_predictions)

            if best_pair is None:
                unmatched_gt.append({
                    "url": gt_item["url"],
                    "gt_name": gt_item["name"],
                    "gt_type": gt_item["type"],
                })
                continue

            best_pairs.append(best_pair)

        case_by_case = [
            {
                "url": p.url,
                "gt_name": p.gt_name,
                "gt_type": p.gt_type,
                "pred_name": p.pred_name,
                "pred_type": p.pred_type,
                "exact_name_match": p.exact_name_match,
                "exact_type_match": p.exact_type_match,
                "exact_match": p.exact_match,
                "prediction_rank": p.prediction_rank,
                "name_similarity": p.name_similarity,
                "class_distance": p.class_distance,
                "class_similarity": p.class_similarity,
                "global_similarity": p.global_similarity,
            }
            for p in best_pairs
        ]

        report = {
            "config": {
                "ground_truth": str(ground_truth_path),
                "predictions": str(predictions_path),
                "name_weight": self.name_weight,
                "class_weight": self.class_weight,
                "soft_threshold": SOFT_THRESHOLD,
            },
            "dataset_summary": {
                "total_ground_truth_cases": len(gt_items),
                "total_prediction_entities": len(pred_items),
                "matched_cases": len(best_pairs),
                "unmatched_gt_cases": len(unmatched_gt),
            },
            "summary": self.compute_summary(best_pairs),
            "by_gt_type": self.compute_by_gt_type(best_pairs),
            "case_by_case": case_by_case,
            "unmatched_ground_truth": unmatched_gt,
        }

        return report