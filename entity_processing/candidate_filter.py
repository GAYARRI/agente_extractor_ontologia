from typing import Any, Dict, Tuple

from .config import CLASS_NAME_ANCHORS, MONUMENT_NAME_ANCHORS
from .name_cleaner import is_plausible_class_name, looks_like_bad_name
from .normalize import normalized_token_text
from .text_cleaning import clean_text


STRICT_PAGE_TYPES = {"listing_page", "category_page", "blog_page", "professional_page"}
UTILITY_NAME_EXACT = {
    "contacta con nosotros",
    "contacto",
    "informacion practica",
    "información práctica",
    "burgos centro",
    "planifica tu viaje",
    "que hacer",
    "qué hacer",
    "que ver",
    "qué ver",
}
NON_FINAL_CLASSES = {"Unknown", "Concept", "ContentPage", "CategoryPage"}
TRUNCATED_TAILS = (" de", " del", " la", " el", " los", " las", " y")
TRUNCATED_HEADS = ("de ", "del ", "y ")
CONTEXT_FRAGMENT_TOKENS = {
    "continuamos",
    "cruzando",
    "datos api",
    "api",
}
OUT_OF_SCOPE_NAME_TOKENS = {
    "madrid",
}
CLASS_ANCHOR_WORDS = {
    "archivo",
    "capilla",
    "catedral",
    "convento",
    "fuente",
    "hospital",
    "iglesia",
    "mercado",
    "monasterio",
    "museo",
    "palacio",
    "parque",
    "plaza",
    "puente",
    "ruta",
    "teatro",
}


def should_keep_candidate(entity: Dict[str, Any], page_type: str) -> Tuple[bool, str]:
    name = clean_text(entity.get("name") or "").strip()
    normalized_name = normalized_token_text(name)
    primary = str(entity.get("primaryClass") or entity.get("class") or entity.get("type") or "").strip()
    description = clean_text(
        entity.get("description")
        or entity.get("shortDescription")
        or entity.get("longDescription")
        or ""
    ).strip()
    mention_role = str(entity.get("mentionRole") or "").strip()

    if not name:
        return False, "missing_name"

    if normalized_name.endswith(TRUNCATED_TAILS) or normalized_name.startswith(TRUNCATED_HEADS):
        return False, "truncated_name_tail"

    if any(token in normalized_name for token in CONTEXT_FRAGMENT_TOKENS):
        return False, "context_fragment_name"

    if any(token in normalized_name for token in OUT_OF_SCOPE_NAME_TOKENS):
        return False, "out_of_scope_name"

    if normalized_name in UTILITY_NAME_EXACT:
        return False, "utility_or_navigation_page"

    if not primary:
        return False, "missing_primary_class"

    if primary in NON_FINAL_CLASSES:
        return False, "non_final_generic_class"

    if mention_role == "related_entity" and page_type in STRICT_PAGE_TYPES:
        return False, f"related_entity_on_{page_type}"

    if (primary in CLASS_NAME_ANCHORS or primary == "Monument") and not is_plausible_class_name(name, primary):
        return False, f"implausible_{primary.lower()}_name"

    if primary == "Cathedral":
        if not (
            normalized_name.startswith("catedral ")
            or normalized_name.startswith("conjunto catedralicio")
        ):
            return False, "implausible_cathedral_structure"
        if normalized_name == "catedral":
            return False, "generic_cathedral_name"

    if primary == "Castle":
        if not (
            normalized_name.startswith("castillo de ")
            or normalized_name.startswith("castillo del ")
            or normalized_name.startswith("castillo de la ")
            or normalized_name.startswith("castillo de los ")
            or normalized_name.startswith("castillo de las ")
        ):
            return False, "implausible_castle_structure"

    if primary == "Monument" and page_type in STRICT_PAGE_TYPES:
        if not any(anchor in normalized_name for anchor in MONUMENT_NAME_ANCHORS):
            return False, f"generic_monument_on_{page_type}"

    if page_type in STRICT_PAGE_TYPES:
        if looks_like_bad_name(name):
            return False, "bad_name_pattern_on_strict_page"

        anchor_count = sum(1 for token in CLASS_ANCHOR_WORDS if token in normalized_name.split())
        if anchor_count >= 2 and not normalized_name.startswith(("ruta ", "rutas ")):
            return False, "composite_navigation_name_on_strict_page"

        if primary in {"Place", "Service", "Organization"} and len(name.split()) > 6:
            return False, f"generic_on_{page_type}"

        if len(name.split()) > 10:
            return False, f"name_too_long_on_{page_type}"

        description_norm = normalized_token_text(description)
        if len(description) > 0 and len(description.split()) > 120 and "categorias" in description_norm:
            return False, f"listing_description_on_{page_type}"

    return True, "keep"
