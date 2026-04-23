from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import urlparse

import requests
from rdflib import Graph, RDF, RDFS, OWL, URIRef, Literal

OFFICIAL_SEGITTUR_CORE_NT = "https://ontologia.segittur.es/turismo/def/core/ontology.nt"
OFFICIAL_SEGITTUR_CORE_NS = "https://ontologia.segittur.es/turismo/def/core#"

GENERIC_NON_ONTOLOGY_TYPES = {
    "Unknown",
    "Location",
    "Place",
    "Thing",
    "Entity",
    "Item",
    "",
}

ONTOLOGY_ALIASES = {
    "segittur": OFFICIAL_SEGITTUR_CORE_NT,
    "segittur_core": OFFICIAL_SEGITTUR_CORE_NT,
    "official_segittur": OFFICIAL_SEGITTUR_CORE_NT,
    "official_segittur_core": OFFICIAL_SEGITTUR_CORE_NT,
}

CLASS_ALIASES = {
    "organisation": "Organization",
    "organization": "Organization",
    "guidedtour": "GuidedTour",
    "tour": "GuidedTour",
    "event": "Event",
    "festival": "Festival",
    "celebration": "Celebration",
    "route": "Route",
    "ruta": "Route",
}


def local_name(uri) -> str:
    value = str(uri or "").strip()
    if not value:
        return ""
    if "#" in value:
        return value.split("#")[-1].strip()
    return value.rstrip("/").split("/")[-1].strip()


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
    if low.endswith('.nt'):
        return 'nt'
    if low.endswith('.ttl'):
        return 'turtle'
    if low.endswith('.rdf') or low.endswith('.owl') or low.endswith('.xml'):
        return 'xml'
    return None


def _load_graph(source: str) -> Graph:
    normalized_source = _normalize_source(source)
    rdf_format = _guess_rdf_format(normalized_source)
    g = Graph()

    try:
        g.parse(normalized_source, format=rdf_format)
        return g
    except Exception:
        if not _is_url(normalized_source):
            raise

    response = requests.get(normalized_source, timeout=30)
    response.raise_for_status()
    data = response.text
    g.parse(data=data, format=rdf_format or 'xml')
    return g


def _literal_by_lang(graph: Graph, subject: URIRef, predicate: URIRef, langs=("es", "en")) -> str:
    literals: List[Literal] = [obj for obj in graph.objects(subject, predicate) if isinstance(obj, Literal)]
    for lang in langs:
        for lit in literals:
            if getattr(lit, 'language', None) == lang:
                return str(lit)
    for lit in literals:
        if getattr(lit, 'language', None) in (None, ''):
            return str(lit)
    return ""


def extract_ontology_catalog(ontology_path: str) -> Dict[str, Dict]:
    g = _load_graph(ontology_path)
    classes: Dict[str, Dict] = {}

    class_uris = set()
    class_uris.update(s for s in g.subjects(RDF.type, OWL.Class) if isinstance(s, URIRef))
    class_uris.update(s for s in g.subjects(RDF.type, RDFS.Class) if isinstance(s, URIRef))

    for cls in sorted(class_uris, key=lambda x: local_name(x).lower()):
        name = local_name(cls)
        if not name or name in {"Class", "Resource", "Thing", "Entity", "Item"}:
            continue

        parents = []
        for parent in g.objects(cls, RDFS.subClassOf):
            if isinstance(parent, URIRef):
                pname = local_name(parent)
                if pname and pname not in parents:
                    parents.append(pname)

        classes[name] = {
            "name": name,
            "uri": str(cls),
            "label_es": _literal_by_lang(g, cls, RDFS.label, ("es", "en")),
            "label_en": _literal_by_lang(g, cls, RDFS.label, ("en", "es")),
            "comment_es": _literal_by_lang(g, cls, RDFS.comment, ("es", "en")),
            "comment_en": _literal_by_lang(g, cls, RDFS.comment, ("en", "es")),
            "parents": parents,
            "ancestors": [],
        }

    def resolve_ancestors(name: str, seen=None) -> List[str]:
        seen = seen or set()
        if name in seen:
            return []
        seen.add(name)
        meta = classes.get(name) or {}
        ordered = []
        for parent in meta.get('parents', []):
            if parent and parent not in ordered:
                ordered.append(parent)
            for anc in resolve_ancestors(parent, seen):
                if anc and anc not in ordered:
                    ordered.append(anc)
        return ordered

    for name in list(classes.keys()):
        classes[name]['ancestors'] = resolve_ancestors(name)

    return classes


def load_valid_classes_from_ontology(ontology_path: str) -> Set[str]:
    return set(extract_ontology_catalog(ontology_path).keys())


def normalize_types_list(values) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    elif not isinstance(values, list):
        values = [values]

    out: List[str] = []
    seen = set()
    for value in values:
        text = str(value or '').strip()
        if not text:
            continue
        short = local_name(text)
        if short and short not in seen:
            seen.add(short)
            out.append(short)
    return out


def normalize_class_candidate(value: str, valid_classes: Set[str]) -> str:
    short = local_name(value)
    if not short:
        return ''
    if short in valid_classes:
        return short
    alias = CLASS_ALIASES.get(short.lower(), short)
    if alias in valid_classes:
        return alias
    return ''


def choose_route_like_class(valid_classes: Set[str]) -> str:
    for candidate in ('Route', 'Ruta', 'Itinerary', 'DestinationExperience'):
        if candidate in valid_classes:
            return candidate
    return 'Unknown'


def choose_event_class(valid_classes: Set[str]) -> str:
    for candidate in ('Event', 'Festival', 'Celebration'):
        if candidate in valid_classes:
            return candidate
    return 'Unknown'


def enforce_closed_world_types(entity: dict, valid_classes: Set[str], ontology_catalog: Optional[Dict[str, Dict]] = None) -> dict:
    ontology_catalog = ontology_catalog or {}
    raw_types = normalize_types_list(entity.get('types') or entity.get('type') or [])
    raw_class = local_name(entity.get('class') or '')
    raw_semantic_type = local_name(entity.get('semantic_type') or '')

    candidates: List[str] = []
    for candidate in [raw_class, raw_semantic_type, *raw_types]:
        normalized = normalize_class_candidate(candidate, valid_classes)
        if normalized and normalized not in candidates:
            candidates.append(normalized)

    valid_specific = [c for c in candidates if c in valid_classes and c not in GENERIC_NON_ONTOLOGY_TYPES]
    final_class = valid_specific[0] if valid_specific else None
    final_types = [final_class] if final_class else []

    meta = ontology_catalog.get(final_class or '', {})
    entity['types_raw'] = raw_types
    entity['class_raw'] = raw_class
    entity['class'] = final_class
    entity['type'] = final_class
    entity['types'] = final_types
    entity['classUri'] = meta.get('uri', '') if final_class else ''
    entity['classAncestors'] = meta.get('ancestors', []) if final_class else []
    entity['classParents'] = meta.get('parents', []) if final_class else []
    entity['ontologyMatch'] = bool(final_class)
    entity['ontologyRejectionReason'] = None if final_class else 'no_matching_segittur_class'
    entity['sourceOntology'] = _normalize_source(entity.get('sourceOntology') or OFFICIAL_SEGITTUR_CORE_NT)
    return entity


def enforce_closed_world_batch(entities: Iterable[dict], valid_classes: Set[str], ontology_catalog: Optional[Dict[str, Dict]] = None) -> List[dict]:
    fixed = []
    for entity in entities or []:
        if not isinstance(entity, dict):
            continue
        fixed.append(enforce_closed_world_types(entity, valid_classes, ontology_catalog=ontology_catalog))
    return fixed
from __future__ import annotations

import os
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse

OFFICIAL_SEGITTUR_CORE_NT = "https://ontologia.segittur.es/turismo/def/core/ontology.nt"

GENERIC_NON_ONTOLOGY_TYPES: Set[str] = {
    "",
    "Unknown",
    "Thing",
    "Location",
    "Place",
    "Entity",
    "Item",
    "Concept",
    "ConceptualObject",
    "TourismEntity",
    "TourismResource",
    "Resource",
    "Agent",
}

CLASS_ALIASES: Dict[str, str] = {
    "concept": "ConceptScheme",
    "conceptscheme": "ConceptScheme",
    "route": "Route",
    "ruta": "Route",
    "event": "Event",
    "evento": "Event",
    "townhall": "TownHall",
    "town_hall": "TownHall",
    "cityhall": "TownHall",
    "city_hall": "TownHall",
    "cathedral": "Cathedral",
    "church": "Church",
    "chapel": "Chapel",
    "basilica": "Basilica",
    "museum": "Museum",
    "palace": "Palace",
    "castle": "Castle",
    "square": "Square",
    "garden": "Garden",
    "park": "Park",
    "monument": "Monument",
    "hotel": "Hotel",
    "hostel": "Hostel",
    "camping": "Camping",
    "restaurant": "Restaurant",
    "touristinformationoffice": "TouristInformationOffice",
    "tourisminformationoffice": "TouristInformationOffice",
    "tourisminformationpoint": "TouristInformationOffice",
    "destinationexperience": "DestinationExperience",
    "guidedtour": "DestinationExperience",
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
    "capilla": "Chapel",
    "basílica": "Basilica",
    "basilica": "Basilica",
    "museo": "Museum",
    "palacio": "Palace",
    "castillo": "Castle",
    "plaza": "Square",
    "jardín": "Garden",
    "jardin": "Garden",
    "parque": "Park",
    "ruta": "Route",
    "camino": "Route",
    "festival": "Event",
    "feria": "Event",
    "evento": "Event",
    "hotel": "Hotel",
    "hostal": "Hostel",
    "albergue": "Hostel",
    "camping": "Camping",
    "restaurante": "Restaurant",
}


def _normalize_source(value: str) -> str:
    value = str(value or "").strip()
    return value or OFFICIAL_SEGITTUR_CORE_NT


def local_name(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    value = value.split("#")[-1]
    value = value.split("/")[-1]
    return value.strip()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def slugify(text: str) -> str:
    text = normalize_whitespace(text).lower()
    text = re.sub(r"[^a-z0-9áéíóúñü]+", "", text, flags=re.IGNORECASE)
    return text


def normalize_types_list(value) -> List[str]:
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]

    out: List[str] = []
    seen: Set[str] = set()

    for item in raw:
        item_local = local_name(item)
        if not item_local:
            continue
        if item_local not in seen:
            seen.add(item_local)
            out.append(item_local)

    return out


def _build_slug_index(valid_classes: Set[str]) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for cls in valid_classes or set():
        index[slugify(cls)] = cls
    return index


def _canonicalize_known_alias(candidate: str) -> str:
    key = slugify(candidate)
    return CLASS_ALIASES.get(key, candidate)


def normalize_class_candidate(candidate: str, valid_classes: Set[str]) -> Optional[str]:
    candidate = local_name(candidate)
    candidate = normalize_whitespace(candidate)

    if not candidate:
        return None

    candidate = _canonicalize_known_alias(candidate)
    slug_index = _build_slug_index(valid_classes)

    if candidate in valid_classes:
        return candidate

    cand_slug = slugify(candidate)
    if cand_slug in slug_index:
        return slug_index[cand_slug]

    if candidate in GENERIC_NON_ONTOLOGY_TYPES:
        return None
    if cand_slug in {slugify(x) for x in GENERIC_NON_ONTOLOGY_TYPES}:
        return None

    return None


def choose_route_like_class(valid_classes: Set[str]) -> str:
    preferred = [
        "Route",
        "Itinerary",
        "TouristRoute",
        "PilgrimageRoute",
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
    ]
    for cls in preferred:
        if cls in valid_classes:
            return cls
    return "Unknown"


def _extract_declared_classes_from_rdf(content: str) -> Set[str]:
    classes: Set[str] = set()

    patterns = [
        re.compile(r"<[^>]+[#/]([A-Za-z][A-Za-z0-9_]*)>\s+a\s+owl:Class", re.IGNORECASE),
        re.compile(r"<[^>]+[#/]([A-Za-z][A-Za-z0-9_]*)>\s+a\s+rdfs:Class", re.IGNORECASE),
        re.compile(r":([A-Za-z][A-Za-z0-9_]*)\s+a\s+owl:Class", re.IGNORECASE),
        re.compile(r":([A-Za-z][A-Za-z0-9_]*)\s+a\s+rdfs:Class", re.IGNORECASE),
    ]

    for pattern in patterns:
        for match in pattern.findall(content or ""):
            classes.add(match)

    return classes


def _extract_subclass_edges(content: str) -> List[Tuple[str, str]]:
    edges: List[Tuple[str, str]] = []

    patterns = [
        re.compile(
            r"<[^>]+[#/]([A-Za-z][A-Za-z0-9_]*)>\s+rdfs:subClassOf\s+<[^>]+[#/]([A-Za-z][A-Za-z0-9_]*)>",
            re.IGNORECASE,
        ),
        re.compile(
            r":([A-Za-z][A-Za-z0-9_]*)\s+rdfs:subClassOf\s+:([A-Za-z][A-Za-z0-9_]*)",
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:
        for child, parent in pattern.findall(content or ""):
            edges.append((child, parent))

    return edges


def _compute_ancestors(cls: str, parents_map: Dict[str, List[str]]) -> List[str]:
    visited: Set[str] = set()
    ordered: List[str] = []

    def dfs(node: str) -> None:
        for parent in parents_map.get(node, []):
            if parent in visited:
                continue
            visited.add(parent)
            ordered.append(parent)
            dfs(parent)

    dfs(cls)
    return ordered


def extract_ontology_catalog(ontology_path: str) -> Dict[str, Dict]:
    if not ontology_path or not os.path.exists(ontology_path):
        return {}

    try:
        with open(ontology_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(ontology_path, "r", encoding="latin-1") as f:
            content = f.read()

    classes = _extract_declared_classes_from_rdf(content)
    subclass_edges = _extract_subclass_edges(content)

    parents_map: Dict[str, List[str]] = {cls: [] for cls in classes}
    for child, parent in subclass_edges:
        parents_map.setdefault(child, [])
        if parent not in parents_map[child]:
            parents_map[child].append(parent)
        if parent not in classes:
            classes.add(parent)
            parents_map.setdefault(parent, [])

    catalog: Dict[str, Dict] = {}

    base_uri = OFFICIAL_SEGITTUR_CORE_NT.replace("/ontology.nt", "#")
    if base_uri.endswith("#") is False:
        base_uri = f"{base_uri}#"

    for cls in sorted(classes):
        parents = parents_map.get(cls, [])
        ancestors = _compute_ancestors(cls, parents_map)

        catalog[cls] = {
            "uri": f"https://ontologia.segittur.es/turismo/def/core#{cls}",
            "parents": parents,
            "ancestors": ancestors,
        }

    return catalog


def load_valid_classes_from_ontology(ontology_path: str) -> Set[str]:
    return set(extract_ontology_catalog(ontology_path).keys())


def _guess_lexical_hint(entity: dict, valid_classes: Set[str]) -> Optional[str]:
    name = normalize_whitespace(
        entity.get("name")
        or entity.get("entity_name")
        or entity.get("label")
        or entity.get("entity")
        or ""
    ).lower()

    if not name:
        return None

    route_cls = choose_route_like_class(valid_classes)
    event_cls = choose_event_class(valid_classes)

    for token, mapped in LEXICAL_HINTS.items():
        if token not in name:
            continue

        if mapped == "Route":
            mapped = route_cls if route_cls != "Unknown" else "Route"
        elif mapped == "Event":
            mapped = event_cls if event_cls != "Unknown" else "Event"

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
        c for c in candidates
        if c in valid_classes and c not in GENERIC_NON_ONTOLOGY_TYPES
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
    fixed = []
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