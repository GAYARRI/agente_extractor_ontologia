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
