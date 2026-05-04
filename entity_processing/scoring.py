from typing import Any, Dict, List, Tuple

from .normalize import normalized_token_text
from .text_cleaning import contains_navigation_noise


PHYSICAL_CLASSES = {
    "Airport",
    "ArcheologicalSite",
    "Bar",
    "Basilica",
    "Bridge",
    "Camping",
    "Castle",
    "Cathedral",
    "Chapel",
    "Church",
    "Convent",
    "Garden",
    "Gate",
    "HistoricalOrCulturalResource",
    "Hostel",
    "Hotel",
    "Monastery",
    "Monument",
    "Museum",
    "Palace",
    "Park",
    "Restaurant",
    "Square",
    "Theatre",
    "Theater",
    "TownHall",
    "TraditionalMarket",
    "Wall",
}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _has_coords(entity: Dict[str, Any]) -> bool:
    coords = entity.get("coordinates") or {}
    return isinstance(coords, dict) and coords.get("lat") is not None and coords.get("lng") is not None


def _has_specific_image(entity: Dict[str, Any]) -> bool:
    image = str(entity.get("mainImage") or entity.get("image") or "").lower()
    if not image:
        return False
    if any(token in image for token in ("desliza.png", "facebook", "whatsapp", "instagram", "youtube", "share")):
        return False

    evidence = entity.get("imageEvidence") or []
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict) and item.get("src") == image and item.get("accepted") is True:
                return True

    weak_tokens = {
        "burgos", "museo", "municipal", "catedral", "iglesia", "palacio",
        "monasterio", "convento", "santa", "maria", "real", "casa",
        "parque", "puente", "hotel", "datos", "api",
    }
    name_tokens = [
        token
        for token in normalized_token_text(entity.get("name")).split()
        if len(token) > 3 and token not in weak_tokens
    ]
    return bool(name_tokens and any(token in image for token in name_tokens))


def _has_image_candidates(entity: Dict[str, Any]) -> bool:
    values = entity.get("candidateImages") or []
    if values:
        return True
    props = entity.get("properties") or {}
    if isinstance(props, dict) and (props.get("candidateImage") or props.get("candidateImages")):
        return True
    return bool(entity.get("candidateImage"))


def _description(entity: Dict[str, Any]) -> str:
    return str(entity.get("description") or entity.get("longDescription") or entity.get("shortDescription") or "")


def ontology_score(entity: Dict[str, Any]) -> float:
    if entity.get("ontologyMatch") is True and entity.get("class"):
        return 1.0
    if entity.get("class"):
        return 0.65
    return 0.0


def extraction_score(entity: Dict[str, Any]) -> float:
    return _as_float(entity.get("extractionScore", entity.get("score")), 0.0)


def quality_score(entity: Dict[str, Any]) -> Tuple[float, List[str]]:
    score = 0.0
    reasons: List[str] = []
    name = str(entity.get("name") or "").strip()
    cls = str(entity.get("primaryClass") or entity.get("class") or "").strip()
    desc = _description(entity).strip()
    page_type = str(entity.get("pageType") or "").strip()
    mention_role = str(entity.get("mentionRole") or "").strip()

    if name:
        score += 1.0
        reasons.append("has_name")
    if 2 <= len(name.split()) <= 8:
        score += 1.0
        reasons.append("good_name_length")
    elif len(name.split()) > 10:
        score -= 1.0
        reasons.append("long_name")

    if cls:
        score += 1.5
        reasons.append("has_class")
    if ontology_score(entity) >= 1.0:
        score += 1.5
        reasons.append("ontology_match")

    if desc:
        score += 1.0
        reasons.append("has_description")
        if len(desc) >= 80:
            score += 0.75
            reasons.append("rich_description")
        if contains_navigation_noise(desc):
            score -= 2.0
            reasons.append("navigation_noise")
    else:
        score -= 1.0
        reasons.append("missing_description")

    if page_type == "place_detail":
        score += 1.0
        reasons.append("place_detail_page")
    elif page_type in {"blog_page", "listing_page", "category_page", "professional_page"}:
        score -= 0.75
        reasons.append(f"weak_page_type:{page_type}")

    if mention_role == "primary_resource":
        score += 1.0
        reasons.append("primary_resource")
    elif mention_role == "related_entity":
        score -= 0.75
        reasons.append("related_entity")

    if _has_coords(entity):
        score += 1.25
        reasons.append("has_coordinates")
    elif cls in PHYSICAL_CLASSES:
        score -= 0.75
        reasons.append("missing_physical_coordinates")

    if _has_specific_image(entity):
        score += 0.75
        reasons.append("specific_image")
    elif _has_image_candidates(entity):
        score -= 0.25
        reasons.append("only_weak_image_candidates")
    elif str(entity.get("imageQuality") or "") in {"missing", "generic", "rejected"}:
        score -= 0.5
        reasons.append("weak_image")

    if entity.get("mergedCount", 1) and int(entity.get("mergedCount") or 1) > 1:
        score += 0.5
        reasons.append("merged_evidence")

    return max(0.0, min(10.0, round(score, 2))), sorted(set(reasons))


def apply_entity_scores(entity: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(entity)
    original = extraction_score(item)
    item["extractionScore"] = original
    item["ontologyScore"] = ontology_score(item)
    q_score, reasons = quality_score(item)
    item["qualityScore"] = q_score
    item["qualityReasons"] = reasons

    normalized_extraction = min(10.0, max(0.0, original * 2.0))
    final = (
        normalized_extraction * 0.2
        + item["ontologyScore"] * 10.0 * 0.3
        + q_score * 0.5
    )
    item["finalScore"] = round(final, 2)
    if item["finalScore"] >= 7.0:
        item["qualityDecision"] = "promote"
    elif item["finalScore"] >= 4.5:
        item["qualityDecision"] = "review"
    else:
        item["qualityDecision"] = "weak"
    return item


def apply_scores(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [apply_entity_scores(entity) for entity in entities]
