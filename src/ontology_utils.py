from __future__ import annotations

from typing import Iterable, List, Set
from rdflib import Graph, RDF, RDFS, OWL


GENERIC_NON_ONTOLOGY_TYPES = {
    "Unknown",
    "Location",
    "Place",
    "Thing",
    "Entity",
    "Item",
    "",
}


def local_name(uri) -> str:
    value = str(uri or "").strip()
    if not value:
        return ""
    if "#" in value:
        return value.split("#")[-1].strip()
    return value.rstrip("/").split("/")[-1].strip()


def load_valid_classes_from_ontology(ontology_path: str) -> Set[str]:
    """
    Extrae las clases válidas desde la ontología RDF/OWL.
    """
    g = Graph()
    g.parse(ontology_path)

    valid_classes: Set[str] = set()

    for s in g.subjects(RDF.type, OWL.Class):
        name = local_name(s)
        if name:
            valid_classes.add(name)

    for s in g.subjects(RDF.type, RDFS.Class):
        name = local_name(s)
        if name:
            valid_classes.add(name)

    # Limpieza mínima de clases meta o demasiado genéricas
    valid_classes = {
        c for c in valid_classes
        if c not in {"Class", "Resource", "Thing", "Entity", "Item"}
    }

    return valid_classes


def normalize_types_list(values) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        values = [str(values)]

    out: List[str] = []
    seen = set()

    for v in values:
        text = str(v or "").strip()
        if not text:
            continue
        short = local_name(text)
        if short and short not in seen:
            seen.add(short)
            out.append(short)

    return out


def choose_route_like_class(valid_classes: Set[str]) -> str:
    """
    Prioridad para rutas/itinerarios/caminos.
    """
    for candidate in ("Route", "Ruta", "DestinationExperience"):
        if candidate in valid_classes:
            return candidate
    return "Unknown"


def choose_event_class(valid_classes: Set[str]) -> str:
    for candidate in ("Event", "Festival", "Celebration"):
        if candidate in valid_classes:
            return candidate
    return "Unknown"


def enforce_closed_world_types(entity: dict, valid_classes: Set[str]) -> dict:
    """
    La salida final solo puede contener clases presentes en la ontología.
    Si hay clases ontológicas específicas válidas, se eliminan Unknown/Location/Place.
    """
    current_types = normalize_types_list(
        entity.get("types") or entity.get("type") or []
    )

    current_class = local_name(entity.get("class") or "")
    candidates = []

    if current_class:
        candidates.append(current_class)

    for t in current_types:
        if t not in candidates:
            candidates.append(t)

    valid_specific = [
        t for t in candidates
        if t in valid_classes and t not in GENERIC_NON_ONTOLOGY_TYPES
    ]

    if valid_specific:
        final_class = valid_specific[0]
        final_types = valid_specific
    else:
        final_class = "Unknown"
        final_types = ["Unknown"]

    entity["class"] = final_class
    entity["type"] = final_types
    entity["types"] = final_types
    return entity


def enforce_closed_world_batch(entities: Iterable[dict], valid_classes: Set[str]) -> List[dict]:
    fixed = []
    for entity in entities or []:
        if not isinstance(entity, dict):
            continue
        fixed.append(enforce_closed_world_types(entity, valid_classes))
    return fixed