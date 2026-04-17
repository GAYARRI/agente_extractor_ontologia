from pathlib import Path
from typing import Any, Dict, List

from .io_utils import save_json
from ..entity_processing.normalize import slugify


def export_by_class(export_dir: Path, entities_by_class: Dict[str, List[dict]]) -> None:
    per_class_dir = export_dir / "by_class"
    per_class_dir.mkdir(parents=True, exist_ok=True)

    for cls, entities in entities_by_class.items():
        out_file = per_class_dir / f"{slugify(cls)}.json"
        save_json(out_file, entities)


def export_audit_buckets(export_dir: Path, audit_buckets: Dict[str, Any]) -> None:
    audit_dir = export_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    for bucket, entities in audit_buckets.items():
        out_file = audit_dir / f"{slugify(bucket)}.json"
        save_json(out_file, entities)


def export_summary(export_dir: Path, summary: Dict[str, Any]) -> None:
    save_json(export_dir / "summary.json", summary)