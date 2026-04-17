from typing import Any, Dict, List

from ..entity_processing.classify import entity_declared_class, entity_specific_classes
from .config import EXPECTED_FIELDS


def has_image(entity: Dict[str, Any]) -> bool:
    return any([
        bool(entity.get("image")),
        bool(entity.get("mainImage")),
        bool(entity.get("images")),
        bool(entity.get("additionalImages")),
    ])


def has_coordinates(entity: Dict[str, Any]) -> bool:
    coords = entity.get("coordinates") or {}
    lat = coords.get("lat")
    lng = coords.get("lng")
    return lat is not None and lng is not None


def has_class_conflict(entity: Dict[str, Any]) -> bool:
    declared = entity_declared_class(entity)
    if not declared:
        return False

    specific = entity_specific_classes(entity)
    if not specific:
        return False

    return declared not in specific


def entity_missing_expected_fields(entity: Dict[str, Any], primary_class: str) -> List[str]:
    missing = []

    for field in EXPECTED_FIELDS.get(primary_class, []):
        if field == "coordinates":
            if not has_coordinates(entity):
                missing.append(field)
        else:
            value = entity.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field)

    return missing