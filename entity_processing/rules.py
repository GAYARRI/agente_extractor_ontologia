import re
from typing import Any, Dict, Tuple

from .config import GENERIC_RESCUE_CANDIDATES
from .normalize import normalize_text


RULES = [
    (r"\bcathedral\b|\bcatedral\b", "Cathedral", "keyword:cathedral"),
    (r"\bbasilica\b|\bbasílica\b", "Basilica", "keyword:basilica"),
    (r"\biglesia\b|\bchurch\b", "Church", "keyword:church"),
    (r"\bmonasterio\b|\bmonastery\b", "Monastery", "keyword:monastery"),
    (r"\bmuseum\b|\bmuseo\b", "Museum", "keyword:museum"),
    (r"\bcastle\b|\bcastillo\b", "Castle", "keyword:castle"),
    (r"\balc[aá]zar\b", "Alcazar", "keyword:alcazar"),
    (r"\bchapel\b|\bcapilla\b", "Chapel", "keyword:chapel"),
    (r"\bplaza\b|\bsquare\b", "Square", "keyword:square"),
    (r"\btown hall\b|\bayuntamiento\b", "TownHall", "keyword:town_hall"),
    (r"\bparque\b|\bpark\b", "Park", "keyword:park"),
    (r"\bjardines\b|\bgarden\b", "Garden", "keyword:garden"),
    (r"\bpuente\b|\bbridge\b", "Bridge", "keyword:bridge"),
    (r"\bpalacio\b|\bpalace\b", "Palace", "keyword:palace"),
    (r"\bmercado\b|\bmarket\b", "Market", "keyword:market"),
    (r"\bteatro\b|\btheatre\b|\btheater\b", "Theatre", "keyword:theatre"),
    (r"\barena\b", "Arena", "keyword:arena"),
    (r"\bfront[oó]n\b", "SportsVenue", "keyword:fronton"),
    (r"\bmurallas\b|\bfortification\b", "Fortification", "keyword:fortification"),
    (r"\bportal\b", "Gate", "keyword:gate"),
    (r"\brestaurant\b|\brestaurante\b|\bbar\b|\bcafeter[ií]a\b", "FoodEstablishment", "keyword:food_place"),
    (r"\bevent\b|\bevento\b|\bfestival\b", "Event", "keyword:event"),
    (r"\bexcursi[oó]n\b|\bexcursion\b", "Excursion", "keyword:excursion"),
    (r"\bruta\b|\broute\b", "Route", "keyword:route"),
    (r"\bsenderismo\b|\bcicloturismo\b|\bactivity\b", "Activity", "keyword:activity"),
    (r"\bbureau\b|\bincoming\b|\bgu[ií]as\b|\bservicio\b|\bservice\b", "TourismService", "keyword:service"),
    (r"\bpostre\b", "Dessert", "keyword:dessert"),
    (r"\blicor\b|\bsidra\b|\bdrink\b", "Drink", "keyword:drink"),
    (r"\bqueso\b|\bfood product\b", "FoodProduct", "keyword:food_product"),
    (r"\bgoxua\b|\bcuajada\b|\bpantxineta\b|\bajoarriero\b|\bfritos\b", "Dish", "keyword:dish"),
]


def build_search_text(entity: Dict[str, Any]) -> str:
    tags = entity.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags]

    breadcrumbs = entity.get("breadcrumbs", [])
    if not isinstance(breadcrumbs, list):
        breadcrumbs = [breadcrumbs]

    parts = [
        entity.get("name", ""),
        entity.get("title", ""),
        entity.get("headline", ""),
        entity.get("description", ""),
        entity.get("shortDescription", ""),
        entity.get("longDescription", ""),
        entity.get("summary", ""),
        entity.get("snippet", ""),
        entity.get("caption", ""),
        entity.get("alt", ""),
        entity.get("category", ""),
        entity.get("subCategory", ""),
        entity.get("seoTitle", ""),
        entity.get("seoDescription", ""),
        entity.get("text", ""),
        entity.get("content", ""),
        entity.get("url", ""),
        " ".join(str(x) for x in tags if x),
        " ".join(str(x) for x in breadcrumbs if x),
    ]
    return normalize_text(" ".join(str(p or "") for p in parts))


def apply_rescue_rules(entity: Dict[str, Any], current_primary: str) -> Tuple[str, bool, str]:
    if current_primary not in GENERIC_RESCUE_CANDIDATES:
        return current_primary, False, ""

    text = build_search_text(entity)
    if not text:
        return current_primary, False, ""

    for pattern, target, reason in RULES:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return target, True, reason

    return current_primary, False, ""