from collections import defaultdict
from typing import Any, Dict, List

from .normalize import normalize_text


GENERIC_FINAL_CLASSES = {"Unknown", "Place", "Concept", "SIN_TIPO", "ContentPage", "CategoryPage"}
CANONICAL_CROSS_PAGE_CLASSES = {
    "TownHall",
    "Cathedral",
    "Church",
    "Chapel",
    "Basilica",
    "Palace",
    "Castle",
    "Museum",
    "Square",
    "Garden",
    "Bridge",
    "Wall",
    "TraditionalMarket",
}
TOWNHALL_EQUIVALENTS = {
    "ayuntamiento de pamplona",
    "ayuntamiento",
    "casa consistorial",
    "ayuntamiento y plaza consistorial",
    "pamplona ayuntamiento",
}


def canonical_entity_name(entity: Dict[str, Any]) -> str:
    name = normalize_text(entity.get("name"))
    primary = str(entity.get("primaryClass") or entity.get("class") or entity.get("type") or "").strip()

    if primary == "TownHall":
        if any(token in name for token in TOWNHALL_EQUIVALENTS):
            return "ayuntamiento de pamplona"
        if "ayuntamiento" in name or "casa consistorial" in name:
            return "ayuntamiento de pamplona"

    return name


def entity_key(entity: Dict[str, Any]) -> str:
    primary = str(entity.get("primaryClass") or entity.get("class") or entity.get("type") or "").strip()
    name = canonical_entity_name(entity)
    if primary in CANONICAL_CROSS_PAGE_CLASSES and name:
        return f"classname|{normalize_text(primary)}|{name}"

    ext_id = (
        entity.get("id")
        or entity.get("externalId")
        or entity.get("url")
        or entity.get("slug")
        or entity.get("canonicalUrl")
        or entity.get("sameAs")
        or entity.get("identifier")
    )
    if ext_id:
        return "id|" + normalize_text(ext_id)

    coords = entity.get("coordinates") or {}
    lat = coords.get("lat")
    lng = coords.get("lng")

    if lat is not None and lng is not None:
        try:
            return f"namecoords|{name}|{round(float(lat), 4)}|{round(float(lng), 4)}"
        except (TypeError, ValueError):
            pass

    return "name|" + name


def group_duplicates(entities: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups = defaultdict(list)
    for entity in entities:
        groups[entity_key(entity)].append(entity)
    return dict(groups)


def choose_best_entity(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    def score(entity: Dict[str, Any]) -> tuple:
        coords = entity.get("coordinates") or {}
        has_coords = coords.get("lat") is not None and coords.get("lng") is not None
        has_image = bool(
            entity.get("image")
            or entity.get("mainImage")
            or entity.get("images")
            or entity.get("additionalImages")
        )
        primary = entity.get("primaryClass") or entity.get("class") or entity.get("type") or ""
        is_specific = primary not in GENERIC_FINAL_CLASSES

        return (
            1 if is_specific else 0,
            1 if bool(entity.get("description") or entity.get("shortDescription") or entity.get("longDescription")) else 0,
            1 if has_coords else 0,
            1 if has_image else 0,
            len(str(entity.get("name", ""))),
        )

    return max(items, key=score)


def dedupe_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups = group_duplicates(entities)
    out = []

    for dedupe_key, items in groups.items():
        winner = dict(choose_best_entity(items))
        winner["dedupeKey"] = dedupe_key
        winner["mergedCount"] = len(items)
        out.append(winner)

    return out
