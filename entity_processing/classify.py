from typing import Any, Dict, Iterable, List, Tuple

from .config import GENERIC_TYPES, TYPE_PRIORITY
from .normalize import clean_type, is_valid_type, sanitize_types


def class_quality(label: str) -> str:
    if label == "SIN_TIPO":
        return "missing"
    if label in GENERIC_TYPES:
        return "generic"
    return "specific"


def iter_class_candidates(entity: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    for source, values in [
        ("class", entity.get("class")),
        ("types", entity.get("types")),
        ("type", entity.get("type")),
        ("primaryClass", entity.get("primaryClass")),
    ]:
        for t in sanitize_types(values):
            yield source, t


def entity_declared_class(entity: Dict[str, Any]) -> str:
    c = clean_type(entity.get("class", ""))
    return c if is_valid_type(c) else ""


def entity_all_classes(entity: Dict[str, Any]) -> List[str]:
    classes = []
    seen = set()

    for _, label in iter_class_candidates(entity):
        if label not in seen:
            seen.add(label)
            classes.append(label)

    return classes or ["SIN_TIPO"]


def entity_primary_class(entity: Dict[str, Any]) -> str:
    candidates = []

    for source, label in iter_class_candidates(entity):
        score = TYPE_PRIORITY.get(label, 50)

        if label not in GENERIC_TYPES:
            score += 15

        if source == "class":
            score += 5
        elif source == "types":
            score += 2
        elif source == "primaryClass":
            score += 7

        candidates.append((score, label))

    if not candidates:
        return "SIN_TIPO"

    candidates.sort(key=lambda x: (-x[0], x[1].lower()))
    return candidates[0][1]