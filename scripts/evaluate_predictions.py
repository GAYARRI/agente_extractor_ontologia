from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Asegura que la raíz del proyecto esté en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from src.evaluation.evaluator import Evaluator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evalúa predicciones con métricas exactas y semánticas."
    )

    parser.add_argument(
        "--ground_truth",
        required=True,
        help="Ruta al ground truth JSON",
    )

    parser.add_argument(
        "--predictions",
        required=True,
        help="Ruta al archivo de predicciones JSON",
    )

    parser.add_argument(
        "--output",
        default="outputs/evaluation_report_semantic.json",
        help="Ruta del reporte de salida",
    )

    parser.add_argument(
        "--name_weight",
        type=float,
        default=0.35,
        help="Peso de la similitud de nombre en global_similarity",
    )

    parser.add_argument(
        "--class_weight",
        type=float,
        default=0.65,
        help="Peso de la similitud de clase en global_similarity",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if abs((args.name_weight + args.class_weight) - 1.0) > 1e-9:
        raise ValueError(
            f"name_weight + class_weight debe sumar 1.0. "
            f"Recibido: {args.name_weight + args.class_weight}"
        )

    evaluator = Evaluator(
        name_weight=args.name_weight,
        class_weight=args.class_weight,
    )

    report = evaluator.evaluate(
        ground_truth_path=args.ground_truth,
        predictions_path=args.predictions,
    )

    evaluator.save_json(args.output, report)

    summary = report.get("summary", {})
    dataset_summary = report.get("dataset_summary", {})

    print(f"[DONE] Reporte guardado en: {args.output}")
    print(f"[INFO] Total GT cases: {dataset_summary.get('total_ground_truth_cases', 0)}")
    print(f"[INFO] Total prediction entities: {dataset_summary.get('total_prediction_entities', 0)}")
    print(f"[INFO] Matched cases: {dataset_summary.get('matched_cases', 0)}")
    print(f"[INFO] Unmatched GT cases: {dataset_summary.get('unmatched_gt_cases', 0)}")
    print(f"[INFO] Exact match accuracy: {summary.get('exact_match_accuracy', 0.0)}")
    print(f"[INFO] Exact type accuracy: {summary.get('exact_type_accuracy', 0.0)}")
    print(f"[INFO] Accuracy@1: {summary.get('accuracy_at_1', 0.0)}")
    print(f"[INFO] Accuracy@2: {summary.get('accuracy_at_2', 0.0)}")
    print(f"[INFO] Mean class distance: {summary.get('mean_class_distance', None)}")
    print(f"[INFO] Mean class similarity: {summary.get('mean_class_similarity', 0.0)}")
    print(f"[INFO] Mean name similarity: {summary.get('mean_name_similarity', 0.0)}")
    print(f"[INFO] Mean global similarity: {summary.get('mean_global_similarity', 0.0)}")


if __name__ == "__main__":
    main()