from typing import Any, Dict

from .config import FAMILY_KEYWORDS
from .normalize import normalize_text


def build_family_text(entity: Dict[str, Any]) -> str:
    parts = [
        entity.get("name", ""),
        entity.get("title", ""),
        entity.get("description", ""),
        entity.get("shortDescription", ""),
        entity.get("longDescription", ""),
        entity.get("url", ""),
        entity.get("primaryClass", ""),
        entity.get("class", ""),
        entity.get("type", ""),
    ]
    return normalize_text(" ".join(str(p or "") for p in parts))


def classify_entity_family(entity: Dict[str, Any]) -> str:
    text = build_family_text(entity)

    for family, keywords in FAMILY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return family

    return "unknown"