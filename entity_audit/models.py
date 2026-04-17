from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Coordinates:
    lat: Optional[float] = None
    lng: Optional[float] = None


@dataclass
class EntityRecord:
    raw: Dict[str, Any]
    name: str = ""
    declared_class: str = ""
    types: List[str] = field(default_factory=list)
    all_classes: List[str] = field(default_factory=list)
    specific_classes: List[str] = field(default_factory=list)
    primary_class: str = "SIN_TIPO"
    class_quality: str = "missing"
    dedupe_key: str = ""
    has_image: bool = False
    has_coordinates: bool = False
    missing_expected_fields: List[str] = field(default_factory=list)
    class_conflict: bool = False
    rescued: bool = False
    rescue_reason: str = ""