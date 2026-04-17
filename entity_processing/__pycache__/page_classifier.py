from typing import Any, Dict

from .config import PAGE_TYPE_PATTERNS
from .normalize import normalize_text


def classify_page(url: str = "", entity: Dict[str, Any] | None = None) -> str:
    url_text = normalize_text(url)
    if entity:
        url_text = url_text or normalize_text(entity.get("url") or entity.get("sourceUrl") or "")

    for page_type, patterns in PAGE_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in url_text:
                return page_type

    return "unknown"