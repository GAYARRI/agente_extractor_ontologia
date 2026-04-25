from __future__ import annotations

import argparse
import csv
from pathlib import Path


TARGET_HEADERS = [
    "id",
    "url",
    "page_family",
    "expected",
    "actual",
    "error_type",
    "notes",
    "proposed_classes",
]


def parse_markdown_row(line: str) -> list[str]:
    text = line.strip().strip('"').strip()
    if not text.startswith("|"):
        return []
    parts = [part.strip() for part in text.split("|")[1:-1]]
    return parts


def normalize_row(parts: list[str]) -> dict[str, str] | None:
    if not parts or parts[0].lower() in {"id", "---"}:
        return None

    row = {
        "id": parts[0] if len(parts) > 0 else "",
        "url": parts[1] if len(parts) > 1 else "",
        "page_family": parts[2] if len(parts) > 2 else "",
        "expected": parts[3] if len(parts) > 3 else "",
        "actual": parts[4] if len(parts) > 4 else "",
        "error_type": parts[5] if len(parts) > 5 else "",
        "notes": parts[6] if len(parts) > 6 else "",
        "proposed_classes": " | ".join(p for p in parts[7:] if p) if len(parts) > 7 else "",
    }
    return row


def normalize_file(input_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw_line in input_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = parse_markdown_row(raw_line)
        row = normalize_row(parts)
        if row:
            rows.append(row)
    return rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TARGET_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normaliza un CSV/Markdown anotado a un CSV estructurado."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="outputs/iteration_sample_autodraft_1.csv",
        help="Archivo anotado de entrada.",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        default="outputs/iteration_sample_autodraft_clean.csv",
        help="CSV limpio de salida.",
    )
    args = parser.parse_args()

    rows = normalize_file(Path(args.input_file))
    write_csv(rows, Path(args.output_file))
    print(f"Rows normalized: {len(rows)}")
    print(f"Output: {args.output_file}")


if __name__ == "__main__":
    main()
