
from typing import Dict, List, Optional, Any


class OntologyReasoner:
    """
    Capa ligera de razonamiento ontológico.
    Funciona aunque OntologyIndex no exponga una API completa:
    - usa aliases y jerarquías internas
    - intenta aprovechar métodos del ontology_index si existen
    - filtra propiedades según la clase resuelta
    """

    DEFAULT_CLASS = "Thing"

    ALIAS_TO_CLASS = {
        "place": "Place",
        "location": "Place",
        "touristattraction": "TouristAttraction",
        "landmark": "Landmark",
        "organization": "Organization",
        "localbusiness": "Organization",
        "service": "Service",
        "event": "Event",
        "person": "Person",
        "concept": "Concept",
        "thing": "Thing",
    }

    NAME_HINTS = [
        ("universidad", "Organization"),
        ("museum", "Place"),
        ("museo", "Place"),
        ("plaza", "Place"),
        ("calle", "Place"),
        ("barrio", "Place"),
        ("isla", "Place"),
        ("puente", "Place"),
        ("hotel", "Organization"),
        ("restaurante", "Organization"),
        ("sevici", "Service"),
    ]

    CLASS_HIERARCHY = {
        "Thing": ["Thing"],
        "Concept": ["Concept", "Thing"],
        "Person": ["Person", "Thing"],
        "Event": ["Event", "Thing"],
        "Service": ["Service", "Thing"],
        "Organization": ["Organization", "Thing"],
        "Place": ["Place", "Location", "Thing"],
        "Landmark": ["Landmark", "Place", "Location", "Thing"],
        "TouristAttraction": ["TouristAttraction", "Place", "Location", "Thing"],
    }

    ALLOWED_PROPERTIES = {
        "Thing": {
            "description", "short_description", "long_description", "relatedUrls",
            "url", "image", "mainImage", "candidateImage", "wikidata_id",
            "name", "type"
        },
        "Concept": {
            "description", "short_description", "long_description", "relatedUrls",
            "url", "name", "type", "wikidata_id"
        },
        "Person": {
            "description", "short_description", "long_description", "relatedUrls",
            "url", "image", "mainImage", "candidateImage", "wikidata_id",
            "name", "type"
        },
        "Event": {
            "description", "short_description", "long_description", "relatedUrls",
            "url", "image", "mainImage", "candidateImage", "wikidata_id",
            "address", "coordinates", "latitude", "longitude", "lon",
            "startDate", "endDate", "openingHours", "name", "type"
        },
        "Service": {
            "description", "short_description", "long_description", "relatedUrls",
            "url", "image", "mainImage", "candidateImage", "wikidata_id",
            "address", "coordinates", "latitude", "longitude", "lon",
            "telephone", "phone", "email", "name", "type"
        },
        "Organization": {
            "description", "short_description", "long_description", "relatedUrls",
            "url", "image", "mainImage", "candidateImage", "wikidata_id",
            "address", "coordinates", "latitude", "longitude", "lon",
            "telephone", "phone", "email", "contactUrls", "name", "type"
        },
        "Place": {
            "description", "short_description", "long_description", "relatedUrls",
            "url", "image", "mainImage", "candidateImage", "wikidata_id",
            "address", "coordinates", "latitude", "longitude", "lon",
            "telephone", "phone", "email", "openingHours", "price", "rating",
            "contactUrls", "name", "type"
        },
        "Landmark": {
            "description", "short_description", "long_description", "relatedUrls",
            "url", "image", "mainImage", "candidateImage", "wikidata_id",
            "address", "coordinates", "latitude", "longitude", "lon",
            "openingHours", "price", "rating", "name", "type"
        },
        "TouristAttraction": {
            "description", "short_description", "long_description", "relatedUrls",
            "url", "image", "mainImage", "candidateImage", "wikidata_id",
            "address", "coordinates", "latitude", "longitude", "lon",
            "openingHours", "price", "rating", "telephone", "phone", "email",
            "name", "type"
        },
    }

    PORTAL_TEXT_BLOCKLIST = {
        "visita sevilla",
        "te queda mucho por descubrir:",
        "estudiar en sevilla - visita sevilla",
        "el flamenco - visita sevilla",
    }

    PORTAL_EMAIL_BLOCKLIST = {
        "visitasevilla@sevillacityoffice.es",
    }

    def __init__(self, ontology_index=None):
        self.ontology_index = ontology_index

    def _norm(self, value: Any) -> str:
        return str(value or "").strip()

    def _norm_key(self, value: Any) -> str:
        return self._norm(value).lower().replace(" ", "").replace("_", "")

    def _norm_text(self, value: Any) -> str:
        return self._norm(value).lower()

    def _normalize_label(self, label: Optional[str]) -> str:
        raw = self._norm(label)
        if not raw:
            return self.DEFAULT_CLASS

        key = self._norm_key(raw)
        if key in self.ALIAS_TO_CLASS:
            return self.ALIAS_TO_CLASS[key]

        # Intenta aprovechar ontology_index si expone alguna API parecida
        if self.ontology_index is not None:
            for method_name in (
                "resolve_class_name",
                "normalize_class_name",
                "get_canonical_class",
                "canonicalize_class",
            ):
                method = getattr(self.ontology_index, method_name, None)
                if callable(method):
                    try:
                        value = method(raw)
                        if value:
                            return self._norm(value)
                    except Exception:
                        pass

        return raw if raw[0].isupper() else raw.capitalize()

    def _guess_from_entity_name(self, entity_name: str, text: str = "") -> Optional[str]:
        name_l = self._norm_text(entity_name)
        text_l = self._norm_text(text)

        if not name_l:
            return None

        if any(x in name_l for x in ("manolo caracol", "niña de los peines", "nina de los peines", "pastora pavón", "pastora pavon")):
            return "Person"

        if "bienal" in name_l and "de flamenco" in text_l:
            return "Event"

        if any(x in name_l for x in ("sevilla", "triana", "altozano", "cartuja")) and len(name_l.split()) <= 4:
            return "Place"

        for hint, klass in self.NAME_HINTS:
            if hint in name_l:
                return klass

        return None

    def resolve_class(self, label: str, entity_name: str = "", text: str = "", props: Optional[dict] = None) -> str:
        props = props or {}
        normalized = self._normalize_label(label)
        guessed = self._guess_from_entity_name(entity_name, text=text)

        # Si nos llega algo demasiado genérico, mejora con pistas del nombre
        if normalized in {"Thing", "Location", "LocalBusiness"} and guessed:
            normalized = guessed

        if normalized == "Location":
            normalized = "Place"

        if normalized == "LocalBusiness":
            normalized = "Organization"

        # Si existen coordenadas pero no tipo claro, favorece Place
        if normalized == "Thing":
            if any(props.get(k) for k in ("latitude", "longitude", "lon")):
                normalized = "Place"

        return normalized or self.DEFAULT_CLASS

    def build_type_hierarchy(self, entity_class: str) -> List[str]:
        entity_class = self.resolve_class(entity_class)
        if entity_class in self.CLASS_HIERARCHY:
            return self.CLASS_HIERARCHY[entity_class][:]

        if self.ontology_index is not None:
            for method_name in ("get_ancestors", "get_superclasses", "superclasses_of"):
                method = getattr(self.ontology_index, method_name, None)
                if callable(method):
                    try:
                        ancestors = method(entity_class)
                        if ancestors:
                            out = [entity_class]
                            for ancestor in ancestors:
                                ancestor = self._norm(ancestor)
                                if ancestor and ancestor not in out:
                                    out.append(ancestor)
                            return out
                    except Exception:
                        pass

        return [entity_class, "Thing"] if entity_class != "Thing" else ["Thing"]

    def allowed_properties(self, entity_class: str) -> set:
        entity_class = self.resolve_class(entity_class)
        hierarchy = self.build_type_hierarchy(entity_class)

        allowed = set()
        for klass in reversed(hierarchy):
            allowed.update(self.ALLOWED_PROPERTIES.get(klass, set()))

        if not allowed:
            allowed = self.ALLOWED_PROPERTIES["Thing"].copy()

        return allowed

    def _is_portal_text(self, value: Any) -> bool:
        text = self._norm_text(value)
        return text in self.PORTAL_TEXT_BLOCKLIST

    def _clean_value(self, key: str, value: Any):
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None

            if key in {"name", "title"} and self._is_portal_text(value):
                return None

            if key == "email" and value.lower() in self.PORTAL_EMAIL_BLOCKLIST:
                return None

            return value

        if isinstance(value, list):
            out = []
            seen = set()
            for item in value:
                cleaned = self._clean_value(key, item)
                if cleaned is None:
                    continue
                norm = str(cleaned).strip().lower()
                if norm not in seen:
                    seen.add(norm)
                    out.append(cleaned)
            return out or None

        return value

    def filter_properties(self, entity_class: str, props: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        props = props if isinstance(props, dict) else {}
        allowed = self.allowed_properties(entity_class)

        filtered = {}
        for key, value in props.items():
            if key not in allowed:
                continue

            cleaned = self._clean_value(key, value)
            if cleaned is None:
                continue

            filtered[key] = cleaned

        return filtered

    def relation_allowed(self, subject_class: str, relation: str, object_class: str) -> bool:
        relation = self._norm_text(relation)
        subject_class = self.resolve_class(subject_class)
        object_class = self.resolve_class(object_class)

        if not relation:
            return False

        if relation in {"locatedin", "islocatedin", "partof"}:
            return object_class in {"Place", "Landmark", "TouristAttraction"}

        if relation in {"hasevent", "hosts", "celebrates"}:
            return object_class == "Event"

        return True
