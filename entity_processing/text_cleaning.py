import re
from typing import Any, Dict


TEXT_FIELDS = (
    "name",
    "rawName",
    "entity_name",
    "entity",
    "label",
    "description",
    "shortDescription",
    "longDescription",
    "short_description",
    "long_description",
    "address",
)


MOJIBAKE_REPLACEMENTS = {
    "Ç?": "Á",
    "Ç­": "á",
    "Ç¸": "é",
    "Çð": "í",
    "Çü": "ó",
    "Ç§": "ú",
    "Çñ": "ñ",
    "ƒ-¬": "",
    "ƒ?o": "\"",
    "ƒ??": "\"",
    "ƒ?": "\"",
    "Â¿": "¿",
    "Â¡": "¡",
    "Â«": "\"",
    "Â»": "\"",
    "Âº": "º",
    "Âª": "ª",
    "Â": "",
}


NAVIGATION_PATTERNS = [
    r"^\s*ES\s*[▼▾]\s*ES\s+EN\s+FR\s+IT\s+PT\s+DE\s+",
    r"^\s*ES\s+ES\s+EN\s+FR\s+IT\s+PT\s+DE\s+",
    r"^\s*ES\s+EN\s+FR\s+IT\s+PT\s+DE\s+",
    r"^\s*Leer\s+m[aá]s\s+",
    r"^\s*Saber\s+m[aá]s\s+",
    r"^\s*Mostrar\s+m[aá]s\s+",
]


INLINE_NOISE_PATTERNS = [
    r"\s+Leer\s+m[aá]s\b.*$",
    r"\s+Mostrar\s+m[aá]s\b.*$",
]


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def repair_mojibake(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    for old, new in MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text


def strip_navigation_noise(value: Any) -> str:
    text = normalize_spaces(value)
    if not text:
        return ""

    previous = None
    while previous != text:
        previous = text
        for pattern in NAVIGATION_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    for pattern in INLINE_NOISE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    text = re.sub(r"\bES\s*[▼▾]\s*ES\s+EN\s+FR\s+IT\s+PT\s+DE\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bES\s+EN\s+FR\s+IT\s+PT\s+DE\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+Ir a\s+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -|,.;:")
    return text


def clean_text(value: Any) -> str:
    return strip_navigation_noise(repair_mojibake(value))


def clean_entity_text_fields(entity: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(entity)
    for field in TEXT_FIELDS:
        if field in item and item.get(field) not in (None, ""):
            item[field] = clean_text(item.get(field))
    return item


def contains_mojibake(value: Any) -> bool:
    return bool(re.search(r"Ç|ƒ|Â", str(value or "")))


def contains_navigation_noise(value: Any) -> bool:
    text = clean_text(value)
    raw = str(value or "")
    return bool(
        re.search(r"ES\s+EN\s+FR\s+IT\s+PT\s+DE", raw, flags=re.IGNORECASE)
        or re.search(r"\b(Saber|Leer|Mostrar)\s+m(?:Ç.s|[aá]s)\b", raw, flags=re.IGNORECASE)
        or re.search(r"\bIr a\b", raw, flags=re.IGNORECASE)
    ) and raw != text
