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
    "Monastery",
    "Convent",
    "Theater",
    "Theatre",
    "Hotel",
    "Hostel",
    "Route",
    "Event",
    "Monument",
    "Chapel",
}
TOWNHALL_EQUIVALENTS = {
    "ayuntamiento de pamplona",
    "ayuntamiento de burgos",
    "ayuntamiento",
    "casa consistorial",
    "ayuntamiento y plaza consistorial",
    "pamplona ayuntamiento",
    "burgos ayuntamiento",
}


def canonical_entity_name(entity: Dict[str, Any]) -> str:
    name = normalize_text(entity.get("canonicalName") or entity.get("name"))
    primary = str(entity.get("primaryClass") or entity.get("class") or entity.get("type") or "").strip()

    if primary == "TownHall":
        if "burgos" in name and any(token in name for token in TOWNHALL_EQUIVALENTS):
            return "ayuntamiento de burgos"
        if "pamplona" in name and any(token in name for token in TOWNHALL_EQUIVALENTS):
            return "ayuntamiento de pamplona"
        if any(token in name for token in TOWNHALL_EQUIVALENTS):
            return "ayuntamiento"

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
        page_type = entity.get("pageType") or ""

        return (
            1 if is_specific else 0,
            1 if page_type == "place_detail" else 0,
            1 if entity.get("mentionRole") == "primary_resource" else 0,
            1 if bool(entity.get("description") or entity.get("shortDescription") or entity.get("longDescription")) else 0,
            1 if has_coords else 0,
            1 if has_image else 0,
            len(str(entity.get("name", ""))),
        )

    return max(items, key=score)


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe_preserve_order(values: List[Any]) -> List[Any]:
    seen = set()
    out = []
    for value in values:
        key = str(value or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def merge_duplicate_group(winner: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(winner)
    source_urls = []
    related_urls = []
    images = []
    candidate_images = []
    rejected_images = []
    image_evidence = []

    for item in items:
        source_urls.extend(_as_list(item.get("sourceUrl")))
        source_urls.extend(_as_list(item.get("url")))
        related_urls.extend(_as_list(item.get("relatedUrls")))
        images.extend(_as_list(item.get("images")))
        images.extend(_as_list(item.get("additionalImages")))
        images.extend(_as_list(item.get("image")))
        images.extend(_as_list(item.get("mainImage")))
        candidate_images.extend(_as_list(item.get("candidateImage")))
        candidate_images.extend(_as_list(item.get("candidateImages")))
        candidate_images.extend(_as_list((item.get("properties") or {}).get("candidateImage") if isinstance(item.get("properties"), dict) else None))
        candidate_images.extend(_as_list((item.get("properties") or {}).get("candidateImages") if isinstance(item.get("properties"), dict) else None))
        rejected_images.extend(_as_list(item.get("rejectedImages")))
        image_evidence.extend(_as_list(item.get("imageEvidence")))

    merged["sourceUrls"] = _dedupe_preserve_order(source_urls)
    merged["relatedUrls"] = _dedupe_preserve_order(_as_list(merged.get("relatedUrls")) + related_urls)

    merged_images = _dedupe_preserve_order(images)
    if merged_images:
        if not merged.get("image"):
            merged["image"] = merged_images[0]
        if not merged.get("mainImage"):
            merged["mainImage"] = merged_images[0]
        merged["images"] = _dedupe_preserve_order(_as_list(merged.get("images")) + merged_images)

    merged["candidateImages"] = _dedupe_preserve_order(_as_list(merged.get("candidateImages")) + candidate_images)
    if rejected_images:
        merged["rejectedImages"] = rejected_images[:20]
    if image_evidence:
        merged["imageEvidence"] = image_evidence[:20]

    return merged


def dedupe_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups = group_duplicates(entities)
    out = []

    for dedupe_key, items in groups.items():
        winner = merge_duplicate_group(choose_best_entity(items), items)
        winner["dedupeKey"] = dedupe_key
        winner["mergedCount"] = len(items)
        out.append(winner)

    return out
