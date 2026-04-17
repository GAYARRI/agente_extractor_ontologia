from typing import Any, Dict

from .config import PAGE_TYPE_PATTERNS
from .normalize import normalize_text


def classify_page(url: str = "", entity: Dict[str, Any] | None = None) -> str:
    url_text = normalize_text(url)
    if entity:
        url_text = url_text or normalize_text(entity.get("url") or entity.get("sourceUrl") or "")

    # Most specific first
    if "/en/lugar/" in url_text or "/lugar/" in url_text:
        return "place_detail"

    if "/en/evento/" in url_text or "/evento/" in url_text:
        return "event_detail"

    if "/lugares/page/" in url_text or "/en/lugares/page/" in url_text:
        return "listing_page"

    if "/tipo-lugar/" in url_text or "/category/" in url_text:
        return "category_page"

    if "/blog" in url_text:
        return "blog_page"

    if "/profesional" in url_text or "/eventos-del-sector" in url_text or "/area-profesional/" in url_text:
        return "professional_page"

    return "unknown"