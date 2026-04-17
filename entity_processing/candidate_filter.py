from typing import Any, Dict, Tuple

from .name_cleaner import looks_like_bad_name
from .normalize import normalized_token_text


STRICT_PAGE_TYPES = {"listing_page", "category_page", "blog_page", "professional_page"}


def should_keep_candidate(entity: Dict[str, Any], page_type: str) -> Tuple[bool, str]:
    name = str(entity.get("name") or "").strip()
    normalized_name = normalized_token_text(name)
    primary = str(entity.get("primaryClass") or entity.get("class") or entity.get("type") or "").strip()
    description = str(
        entity.get("description")
        or entity.get("shortDescription")
        or entity.get("longDescription")
        or ""
    ).strip()

    if not name:
        return False, "missing_name"

    # IMPORTANT: only apply very hard rejection to clearly bad listing/category pages
    if page_type in STRICT_PAGE_TYPES:
        if looks_like_bad_name(name):
            return False, "bad_name_pattern_on_strict_page"

        if primary in {"Unknown", "Place", "Concept", "ContentPage", "CategoryPage"} and len(name.split()) > 6:
            return False, f"generic_on_{page_type}"

        if len(name.split()) > 10:
            return False, f"name_too_long_on_{page_type}"

        if len(description) > 0 and len(description.split()) > 120 and "categorías" in normalized_token_text(description):
            return False, f"listing_description_on_{page_type}"

    # For detail pages, be permissive
    return True, "keep"