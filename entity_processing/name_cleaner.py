import re
from typing import Any, Dict

from .config import BAD_NAME_TOKENS, NAME_STOP_SUFFIXES
from .normalize import normalized_token_text


def extract_raw_name(entity: Dict[str, Any]) -> str:
    return (
        str(
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        ).strip()
    )


def clean_entity_name(raw_name: str) -> str:
    name = str(raw_name or "").strip()

    # cut obvious sentence continuation
    name = re.split(r"[.:;]\s+", name)[0].strip()

    # remove repeated spaces
    name = re.sub(r"\s+", " ", name).strip()

    # remove long mixed tails after strong separators
    for sep in [" – ", " - ", " | "]:
        if sep in name:
            name = name.split(sep)[0].strip()

    tokens = name.split()
    cleaned_tokens = []

    for token in tokens:
        low = normalized_token_text(token)
        if low in NAME_STOP_SUFFIXES and len(cleaned_tokens) >= 2:
            break
        cleaned_tokens.append(token)

    name = " ".join(cleaned_tokens).strip()

    # remove awkward tail words again
    name = re.sub(r"\s+", " ", name).strip()

    return name


def looks_like_bad_name(name: str) -> bool:
    normalized = normalized_token_text(name)

    if not normalized:
        return True

    if len(normalized.split()) > 12:
        return True

    if re.search(r"\b\d+\s*…\s*\d+\b", normalized):
        return True

    bad_hits = sum(1 for token in BAD_NAME_TOKENS if token in normalized)
    if bad_hits >= 2:
        return True

    return False