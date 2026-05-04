import re
from typing import Any, List

from .config import CANONICAL_TYPE_MAP, FORBIDDEN_TYPES
from .text_cleaning import clean_text


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def clean_type(value: Any) -> str:
    raw = normalize_spaces(str(value or ""))
    if not raw:
        return ""
    return CANONICAL_TYPE_MAP.get(raw.lower(), raw)


def is_valid_type(value: str) -> bool:
    cleaned = clean_type(value)
    return bool(cleaned) and cleaned not in FORBIDDEN_TYPES


def sanitize_types(value: Any) -> List[str]:
    out = []
    seen = set()
    for item in as_list(value):
        cleaned = clean_type(item)
        if not is_valid_type(cleaned):
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def normalize_text(value: Any) -> str:
    text = clean_text(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalized_token_text(value: Any) -> str:
    text = normalize_text(value)
    text = re.sub(r"[^\wÀ-ÿ\s/-]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text
