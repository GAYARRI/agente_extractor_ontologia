from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


def load_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_csv(path: str) -> list[dict[str, str]]:
    text = Path(path).read_text(encoding="utf-8")
    delimiter = ";" if ";" in text.splitlines()[0] else ","
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def entity_class(entity: dict) -> str:
    value = entity.get("class") or entity.get("type") or "Unknown"
    if isinstance(value, list):
        value = value[0] if value else "Unknown"
    return str(value or "Unknown")


def normalize(text: str) -> str:
    return (text or "").strip().lower()


def summarize_iteration_sample(rows: list[dict[str, str]], entities_by_url: dict[str, list[dict]]) -> tuple[list[dict], Counter]:
    results = []
    counts = Counter()
    for row in rows:
        url = row.get("url", "").strip()
        entities = entities_by_url.get(url, [])
        current_count = len(entities)
        current_classes = ", ".join(sorted({entity_class(e) for e in entities})) if entities else "0 entidades"
        expected_note = normalize(row.get("notes", ""))
        error_type = normalize(row.get("error_type", ""))
        proposed = normalize(row.get("proposed_classes", ""))
        expected_zero = "debe ignorarse" in expected_note or "disclaimer legal" in expected_note or "0 entidades" in normalize(row.get("actual", ""))

        if expected_zero:
            status = "resolved" if current_count == 0 else "pending"
        elif "validado" in error_type:
            status = "resolved" if current_count > 0 else "regression"
        elif "falso negativo" in error_type:
            status = "resolved" if current_count > 0 else "pending"
        elif "mal clasificado" in error_type:
            if current_count == 0:
                status = "regression"
            elif proposed and any(token and token in normalize(current_classes) for token in proposed.replace("/", " ").split()):
                status = "resolved"
            elif "unknown" not in normalize(current_classes) and "location" not in normalize(current_classes):
                status = "partially_resolved"
            else:
                status = "pending"
        else:
            status = "review"

        counts[status] += 1
        results.append(
            {
                "url": url,
                "expected_issue": row.get("error_type", ""),
                "expected_hint": row.get("notes", ""),
                "current_count": str(current_count),
                "current_classes": current_classes,
                "status": status,
            }
        )
    return results, counts


def summarize_zero_sample(rows: list[dict[str, str]], entities_by_url: dict[str, list[dict]]) -> tuple[list[dict], Counter]:
    results = []
    counts = Counter()
    for row in rows:
        url = row.get("url", "").strip()
        entities = entities_by_url.get(url, [])
        current_count = len(entities)
        current_classes = ", ".join(sorted({entity_class(e) for e in entities})) if entities else "0 entidades"
        decision = normalize(row.get("decision", ""))
        expected = normalize(row.get("expected", ""))

        if "0 entities" in expected or "0 entity" in expected or "listado" in decision or "enlaces" in decision or "se clasifica alli y aqui no" in normalize(row.get("notes", "")):
            should_have_entities = False
        else:
            should_have_entities = True

        if should_have_entities and current_count > 0:
            status = "resolved"
        elif should_have_entities and current_count == 0:
            status = "pending"
        elif not should_have_entities and current_count == 0:
            status = "resolved"
        else:
            status = "regression"

        counts[status] += 1
        results.append(
            {
                "url": url,
                "expected_decision": row.get("decision", ""),
                "expected": row.get("expected", ""),
                "current_count": str(current_count),
                "current_classes": current_classes,
                "status": status,
            }
        )
    return results, counts


def write_report(path: str, iteration_results: list[dict], iteration_counts: Counter, zero_results: list[dict], zero_counts: Counter) -> None:
    lines = [
        "# Comparison Against Reviewed Samples",
        "",
        "## Iteration Sample",
        "",
    ]
    for key in ("resolved", "partially_resolved", "pending", "regression", "review"):
        if iteration_counts.get(key):
            lines.append(f"- `{key}`: `{iteration_counts[key]}`")
    lines.extend(["", "### Pending Or Regression", ""])
    for row in iteration_results:
        if row["status"] in {"pending", "regression"}:
            lines.append(f"- `{row['status']}` | {row['url']}")
            lines.append(f"  Esperado: {row['expected_issue']}")
            lines.append(f"  Actual: {row['current_count']} | {row['current_classes']}")
    lines.extend(["", "## Zero-Entity Shortlist", ""])
    for key in ("resolved", "pending", "regression"):
        if zero_counts.get(key):
            lines.append(f"- `{key}`: `{zero_counts[key]}`")
    lines.extend(["", "### Pending Or Regression", ""])
    for row in zero_results:
        if row["status"] in {"pending", "regression"}:
            lines.append(f"- `{row['status']}` | {row['url']}")
            lines.append(f"  Esperado: {row['expected_decision']} | {row['expected']}")
            lines.append(f"  Actual: {row['current_count']} | {row['current_classes']}")
    lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    entities = load_json("entities.json")
    entities_by_url: dict[str, list[dict]] = {}
    for entity in entities:
        url = str(entity.get("sourceUrl") or entity.get("url") or entity.get("source_url") or "").strip()
        if not url:
            continue
        entities_by_url.setdefault(url, []).append(entity)

    iteration_rows = load_csv("outputs/iteration_sample_autodraft_clean.csv")
    zero_rows = load_csv("outputs/zero_entity_shortlist_clean.csv")

    iteration_results, iteration_counts = summarize_iteration_sample(iteration_rows, entities_by_url)
    zero_results, zero_counts = summarize_zero_sample(zero_rows, entities_by_url)
    write_report("docs/reviewed_samples_comparison.md", iteration_results, iteration_counts, zero_results, zero_counts)
    print("docs/reviewed_samples_comparison.md")


if __name__ == "__main__":
    main()
