from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import urlparse

import requests
from rdflib import Graph, Literal, RDF, RDFS, OWL, URIRef

OFFICIAL_SEGITTUR_CORE_NT = "https://ontologia.segittur.es/turismo/def/core/ontology.nt"
OFFICIAL_SEGITTUR_CORE_NS = "https://ontologia.segittur.es/turismo/def/core#"

GENERIC_NON_ONTOLOGY_TYPES: Set[str] = {
    "",
    "Unknown",
    "Thing",
    "Location",
    "Place",
    "Entity",
    "Item",
    "Concept",
    "ConceptScheme",
    "ConceptualObject",
    "TourismEntity",
    "TourismResource",
    "TourismService",
    "TourismOrganisation",
    "TourismOrRelatedFacility",
    "Resource",
    "Agent",
}

ONTOLOGY_ALIASES = {
    "segittur": OFFICIAL_SEGITTUR_CORE_NT,
    "segittur_core": OFFICIAL_SEGITTUR_CORE_NT,
    "official_segittur": OFFICIAL_SEGITTUR_CORE_NT,
    "official_segittur_core": OFFICIAL_SEGITTUR_CORE_NT,
}

CLASS_ALIASES: Dict[str, str] = {
    "organisation": "TourismOrganisation",
    "organization": "TourismOrganisation",
    "event": "Event",
    "evento": "Event",
    "festival": "Event",
    "celebration": "Event",
    "route": "Route",
    "ruta": "Route",
    "itinerary": "Itinerary",
    "guidedtour": "Tour",
    "guidedtour": "Tour",
    "tour": "Tour",
    "destinationexperience": "DestinationExperience",
    "activity": "DestinationExperience",
    "excursion": "Tour",
    "townhall": "TownHall",
    "cityhall": "TownHall",
    "cathedral": "Cathedral",
    "church": "Church",
    "chapel": "Chapel",
    "basilica": "Basilica",
    "museum": "Museum",
    "palace": "Palace",
    "castle": "Castle",
    "square": "Square",
    "garden": "Garden",
    "park": "NaturalPark",
    "monument": "Monument",
    "bridge": "Bridge",
    "tower": "Tower",
    "wall": "Wall",
    "theatre": "Theater",
    "theater": "Theater",
    "auditorium": "Auditorium",
    "stadium": "Stadium",
    "bullring": "BullRing",
    "restaurant": "Restaurant",
    "bar": "Bar",
    "cafe": "FoodEstablishment",
    "hotel": "Hotel",
    "hostel": "Hostel",
    "camping": "Camping",
    "market": "TraditionalMarket",
    "trainstation": "TrainStation",
    "busstation": "BusStation",
    "airport": "Airport",
    "touristinformationoffice": "TouristInformationOffice",
    "tourisminformationoffice": "TouristInformationOffice",
    "publicservice": "PublicService",
    "medicalclinic": "PublicService",
    "healthcarefacility": "PublicService",
    "healthcareorganization": "PublicService",
    "eventorganisationcompany": "EventOrganisationCompany",
}

LEXICAL_HINTS: Dict[str, str] = {
    "ayuntamiento": "TownHall",
    "catedral": "Cathedral",
    "iglesia": "Church",
    "parroquia": "Church",
    "capilla": "Chapel",
    "basilica": "Basilica",
    "monasterio": "Monastery",
    "convento": "Convent",
    "museo": "Museum",
    "palacio": "Palace",
    "castillo": "Castle",
    "alcazar": "Alcazar",
    "plaza": "Square",
    "jardin": "Garden",
    "jardines": "Garden",
    "parque natural": "NaturalPark",
    "parque": "Garden",
    "puente": "Bridge",
    "muralla": "Wall",
    "torre": "Tower",
    "mercado": "TraditionalMarket",
    "mercadillo": "TraditionalMarket",
    "teatro": "Theater",
    "auditorio": "Auditorium",
    "estadio": "Stadium",
    "plaza de toros": "BullRing",
    "festival": "Event",
    "feria": "Event",
    "evento": "Event",
    "congreso": "Event",
    "exposicion": "Event",
    "concierto": "Event",
    "camino": "Route",
    "ruta": "Route",
    "sendero": "Route",
    "itinerario": "Itinerary",
    "visita guiada": "Tour",
    "tour guiado": "Tour",
    "restaurante": "Restaurant",
    "bar": "Bar",
    "cafeteria": "FoodEstablishment",
    "cafe": "FoodEstablishment",
    "hotel": "Hotel",
    "hostal": "Hostel",
    "albergue": "Hostel",
    "camping": "Camping",
    "estacion de tren": "TrainStation",
    "estacion de autobuses": "BusStation",
    "aeropuerto": "Airport",
    "oficina de turismo": "TouristInformationOffice",
}


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", str(text or ""))
        if unicodedata.category(ch) != "Mn"
    )


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def slugify(text: str) -> str:
    text = _strip_accents(normalize_whitespace(text)).lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def local_name(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if "#" in raw:
        return raw.split("#")[-1].strip()
    return raw.rstrip("/").split("/")[-1].strip()


def _is_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def _normalize_source(source: str) -> str:
    source = str(source or "").strip()
    if not source:
        return OFFICIAL_SEGITTUR_CORE_NT
    return ONTOLOGY_ALIASES.get(source, source)


def _guess_rdf_format(source: str) -> Optional[str]:
    low = str(source or "").lower()
    if low.endswith(".nt"):
        return "nt"
    if low.endswith(".ttl"):
        return "turtle"
    if low.endswith(".rdf") or low.endswith(".owl") or low.endswith(".xml"):
        return "xml"
    return None


def _load_graph(source: str) -> Graph:
    normalized_source = _normalize_source(source)
    rdf_format = _guess_rdf_format(normalized_source)
    graph = Graph()

    try:
        graph.parse(normalized_source, format=rdf_format)
        return graph
    except Exception:
        if not _is_url(normalized_source):
            raise

    response = requests.get(normalized_source, timeout=30)
    response.raise_for_status()
    graph.parse(data=response.text, format=rdf_format or "xml")
    return graph


def _literal_by_lang(graph: Graph, subject: URIRef, predicate: URIRef, langs=("es", "en")) -> str:
    literals: List[Literal] = [
        obj for obj in graph.objects(subject, predicate) if isinstance(obj, Literal)
    ]
    for lang in langs:
        for lit in literals:
            if getattr(lit, "language", None) == lang:
                return str(lit)
    for lit in literals:
        if getattr(lit, "language", None) in (None, ""):
            return str(lit)
    return ""


def extract_ontology_catalog(ontology_path: str) -> Dict[str, Dict]:
    graph = _load_graph(ontology_path)
    classes: Dict[str, Dict] = {}

    class_uris = set()
    class_uris.update(
        subj for subj in graph.subjects(RDF.type, OWL.Class) if isinstance(subj, URIRef)
    )
    class_uris.update(
        subj for subj in graph.subjects(RDF.type, RDFS.Class) if isinstance(subj, URIRef)
    )

    for cls in sorted(class_uris, key=lambda x: local_name(x).lower()):
        name = local_name(cls)
        if not name:
            continue

        parents: List[str] = []
        for parent in graph.objects(cls, RDFS.subClassOf):
            if not isinstance(parent, URIRef):
                continue
            parent_name = local_name(parent)
            if parent_name and parent_name not in parents:
                parents.append(parent_name)

        classes[name] = {
            "name": name,
            "uri": str(cls),
            "label_es": _literal_by_lang(graph, cls, RDFS.label, ("es", "en")),
            "label_en": _literal_by_lang(graph, cls, RDFS.label, ("en", "es")),
            "comment_es": _literal_by_lang(graph, cls, RDFS.comment, ("es", "en")),
            "comment_en": _literal_by_lang(graph, cls, RDFS.comment, ("en", "es")),
            "parents": parents,
            "ancestors": [],
        }

    def resolve_ancestors(name: str, seen: Optional[Set[str]] = None) -> List[str]:
        seen = seen or set()
        if name in seen:
            return []
        seen.add(name)

        ordered: List[str] = []
        meta = classes.get(name) or {}
        for parent in meta.get("parents", []):
            if parent and parent not in ordered:
                ordered.append(parent)
            for ancestor in resolve_ancestors(parent, seen):
                if ancestor and ancestor not in ordered:
                    ordered.append(ancestor)
        return ordered

    for name in list(classes.keys()):
        classes[name]["ancestors"] = resolve_ancestors(name)

    return classes


def load_valid_classes_from_ontology(ontology_path: str) -> Set[str]:
    return set(extract_ontology_catalog(ontology_path).keys())


def normalize_types_list(value) -> List[str]:
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raw_values = [value]

    out: List[str] = []
    seen: Set[str] = set()
    for item in raw_values:
        item_local = local_name(item)
        if not item_local or item_local in seen:
            continue
        seen.add(item_local)
        out.append(item_local)
    return out


def _build_slug_index(valid_classes: Set[str]) -> Dict[str, str]:
    return {slugify(cls): cls for cls in valid_classes or set()}


def _canonicalize_known_alias(candidate: str) -> str:
    key = slugify(candidate)
    return CLASS_ALIASES.get(key, candidate)


def normalize_class_candidate(candidate: str, valid_classes: Set[str]) -> Optional[str]:
    candidate = normalize_whitespace(local_name(candidate))
    if not candidate:
        return None

    if candidate in GENERIC_NON_ONTOLOGY_TYPES:
        return None

    candidate = _canonicalize_known_alias(candidate)
    if candidate in valid_classes:
        return candidate

    slug_index = _build_slug_index(valid_classes)
    candidate_slug = slugify(candidate)
    if candidate_slug in slug_index:
        resolved = slug_index[candidate_slug]
        if resolved not in GENERIC_NON_ONTOLOGY_TYPES:
            return resolved

    return None


def choose_route_like_class(valid_classes: Set[str]) -> str:
    preferred = [
        "Route",
        "Itinerary",
        "Tour",
        "TouristRoute",
        "PilgrimageRoute",
        "Trail",
    ]
    for cls in preferred:
        if cls in valid_classes:
            return cls
    return "Unknown"


def choose_event_class(valid_classes: Set[str]) -> str:
    preferred = [
        "Event",
        "Festival",
        "CulturalEvent",
        "Celebration",
    ]
    for cls in preferred:
        if cls in valid_classes:
            return cls
    return "Unknown"


def _guess_lexical_hint(entity: dict, valid_classes: Set[str]) -> Optional[str]:
    name = normalize_whitespace(
        entity.get("name")
        or entity.get("entity_name")
        or entity.get("label")
        or entity.get("entity")
        or ""
    )
    name_ascii = _strip_accents(name).lower()
    if not name_ascii:
        return None

    route_cls = choose_route_like_class(valid_classes)
    event_cls = choose_event_class(valid_classes)

    for token, mapped in LEXICAL_HINTS.items():
        if token not in name_ascii:
            continue

        if mapped == "Route":
            mapped = route_cls if route_cls != "Unknown" else mapped
        elif mapped == "Event":
            mapped = event_cls if event_cls != "Unknown" else mapped

        normalized = normalize_class_candidate(mapped, valid_classes)
        if normalized:
            return normalized

    return None


def enforce_closed_world_types(
    entity: dict,
    valid_classes: Set[str],
    ontology_catalog: Optional[Dict[str, Dict]] = None,
) -> dict:
    ontology_catalog = ontology_catalog or {}

    raw_types = normalize_types_list(entity.get("types") or entity.get("type") or [])
    raw_class = local_name(entity.get("class") or "")
    raw_semantic_type = local_name(entity.get("semantic_type") or "")

    candidates: List[str] = []
    for candidate in [raw_class, raw_semantic_type, *raw_types]:
        normalized = normalize_class_candidate(candidate, valid_classes)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    lexical_hint = _guess_lexical_hint(entity, valid_classes)
    if lexical_hint and lexical_hint not in candidates:
        candidates.insert(0, lexical_hint)

    valid_specific = [
        candidate
        for candidate in candidates
        if candidate in valid_classes and candidate not in GENERIC_NON_ONTOLOGY_TYPES
    ]

    final_class = valid_specific[0] if valid_specific else None
    final_types = [final_class] if final_class else []
    meta = ontology_catalog.get(final_class or "", {})

    entity["types_raw"] = raw_types
    entity["class_raw"] = raw_class
    entity["semantic_type_raw"] = raw_semantic_type
    entity["closed_world_candidates"] = candidates
    entity["closed_world_lexical_hint"] = lexical_hint or ""

    entity["class"] = final_class
    entity["type"] = final_class
    entity["types"] = final_types

    entity["classUri"] = meta.get("uri", "") if final_class else ""
    entity["classAncestors"] = meta.get("ancestors", []) if final_class else []
    entity["classParents"] = meta.get("parents", []) if final_class else []
    entity["ontologyMatch"] = bool(final_class)
    entity["ontologyRejectionReason"] = None if final_class else "no_matching_segittur_class"
    entity["sourceOntology"] = _normalize_source(
        entity.get("sourceOntology") or OFFICIAL_SEGITTUR_CORE_NT
    )
    return entity


def enforce_closed_world_batch(
    entities: Iterable[dict],
    valid_classes: Set[str],
    ontology_catalog: Optional[Dict[str, Dict]] = None,
) -> List[dict]:
    fixed: List[dict] = []
    for entity in entities or []:
        if not isinstance(entity, dict):
            continue
        fixed.append(
            enforce_closed_world_types(
                entity,
                valid_classes,
                ontology_catalog=ontology_catalog,
            )
        )
    return fixed
