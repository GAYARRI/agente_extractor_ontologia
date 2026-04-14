from pathlib import Path
from datetime import datetime
import argparse
import json

from src.evaluation.evaluator import load_json, save_json, evaluate_predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark evaluation")
    parser.add_argument("--ground-truth", required=True, help="Path to ground truth JSON")
    parser.add_argument("--predictions", required=True, help="Path to predictions JSON")
    parser.add_argument("--output", default="benchmark/reports", help="Output folder")
    parser.add_argument("--threshold", type=float, default=0.86, help="Entity matching threshold")
    args = parser.parse_args()

    gt = load_json(args.ground_truth)
    preds = load_json(args.predictions)

    report = evaluate_predictions(
        ground_truth_records=gt,
        prediction_records=preds,
        threshold=args.threshold,
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / f"evaluation_{ts}.json"
    save_json(report, report_path)

    summary_path = output_dir / f"evaluation_{ts}.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        gm = report["global_metrics"]
        f.write("# Benchmark evaluation\n\n")
        f.write(f"- Pages evaluated: {gm['pages_evaluated']}\n")
        f.write(f"- TP: {gm['tp']}\n")
        f.write(f"- FP: {gm['fp']}\n")
        f.write(f"- FN: {gm['fn']}\n")
        f.write(f"- Precision: {gm['precision']}\n")
        f.write(f"- Recall: {gm['recall']}\n")
        f.write(f"- F1: {gm['f1']}\n")
        f.write(f"- Type accuracy: {gm['type_accuracy']}\n\n")

        f.write("## Property metrics\n\n")
        for prop, metrics in gm["property_metrics"].items():
            f.write(
                f"- {prop}: {metrics['correct']}/{metrics['total']} "
                f"(accuracy={metrics['accuracy']})\n"
            )

        f.write("\n## Per-type metrics\n\n")
        for entity_type, metrics in gm["per_type_metrics"].items():
            f.write(
                f"- {entity_type}: TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']} "
                f"P={metrics['precision']} R={metrics['recall']} F1={metrics['f1']}\n"
            )

    print(f"Report saved to: {report_path}")
    print(f"Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()