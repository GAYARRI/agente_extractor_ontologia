from __future__ import annotations

import argparse
import csv
from pathlib import Path


TARGET_HEADERS = [
    "priority",
    "family",
    "url",
    "why_review",
    "expected",
    "actual",
    "decision",
    "notes",
]


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimiter)
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized = {key: (row.get(key) or "").strip() for key in TARGET_HEADERS}
            if not any(normalized.values()):
                continue
            rows.append(normalized)
        return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TARGET_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normaliza el shortlist anotado de zero entities a CSV limpio.")
    parser.add_argument("input_file", nargs="?", default="zero-entity_ShortList.csv")
    parser.add_argument("output_file", nargs="?", default="outputs/zero_entity_shortlist_clean.csv")
    args = parser.parse_args()

    rows = load_rows(Path(args.input_file))
    write_csv(rows, Path(args.output_file))
    print(f"Rows normalized: {len(rows)}")
    print(f"Output: {args.output_file}")


if __name__ == "__main__":
    main()
