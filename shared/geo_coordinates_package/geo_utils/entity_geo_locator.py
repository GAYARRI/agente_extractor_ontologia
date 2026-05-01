from typing import Any, Dict

from .nominatim_resolver import HybridGeoResolver
from .tourism_property_extractor import TourismPropertyExtractor


class EntityGeoLocator:
    def __init__(self, default_city: str = "Madrid", cache_path: str = "cache/geo_resolver_cache.json"):
        self.property_extractor = TourismPropertyExtractor()
        self.geo_resolver = HybridGeoResolver(default_city=default_city, cache_path=cache_path)

    def _has_valid_coordinates(self, coords: Any) -> bool:
        return isinstance(coords, dict) and coords.get("lat") is not None and coords.get("lng") is not None

    def _geo_resolver_class_hint(self, entity_type: str) -> str:
        value = str(entity_type or "").strip().lower()
        if value in {"hotel", "restaurant", "bar", "traditionalmarket", "shop"}:
            return "Organization"
        if value in {"route", "event", "person", "concept", "thing", "unknown", ""}:
            return ""
        return "Place"

    def _is_geo_candidate_entity(self, entity: Dict[str, Any]) -> bool:
        entity_type = str(entity.get("class") or entity.get("type") or "").strip().lower()
        allowed_types = {
            "townhall",
            "cathedral",
            "church",
            "museum",
            "palace",
            "castle",
            "square",
            "garden",
            "stadium",
            "hotel",
            "restaurant",
            "traditionalmarket",
            "monument",
            "bridge",
            "wall",
            "gate",
            "naturalresource",
            "historicalorculturalresource",
        }
        return entity_type in allowed_types and bool(entity.get("name") or entity.get("entity_name"))

    def locate(self, entity: Dict[str, Any], html: str = "", text: str = "", url: str = "") -> Dict[str, Any]:
        props = self.property_extractor.extract(entity=entity, text=text, html=html, url=url)
        coords = props.get("coordinates") if isinstance(props, dict) else None

        result: Dict[str, Any] = {}
        if self._has_valid_coordinates(coords):
            result["coordinates"] = coords
            result["latitude"] = coords["lat"]
            result["longitude"] = coords["lng"]
            result["geo_source"] = ((props.get("debug") or {}).get("geo_source") if isinstance(props, dict) else None)
            return result

        if not self._is_geo_candidate_entity(entity):
            return result

        name = str(entity.get("name") or entity.get("entity_name") or entity.get("label") or "").strip()
        address = str(
            entity.get("address")
            or ((entity.get("properties") or {}).get("address") if isinstance(entity.get("properties"), dict) else "")
            or ""
        ).strip()

        resolved = self.geo_resolver.resolve(
            entity_name=name,
            address=address,
            source_url=url,
            entity_class=self._geo_resolver_class_hint(entity.get("class") or entity.get("type")),
        )

        if resolved.get("lat") is None or resolved.get("lng") is None:
            return result

        result["coordinates"] = {"lat": float(resolved["lat"]), "lng": float(resolved["lng"])}
        result["latitude"] = result["coordinates"]["lat"]
        result["longitude"] = result["coordinates"]["lng"]
        result["geo_source"] = resolved.get("source")
        if resolved.get("query"):
            result["geo_query"] = resolved.get("query")
        if resolved.get("wikidata_id"):
            result["wikidata_id"] = resolved.get("wikidata_id")
        return result
