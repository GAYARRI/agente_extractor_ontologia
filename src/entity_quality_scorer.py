from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


class EntityQualityScorer:
    def __init__(self) -> None:
        self.stop_tokens = {"de", "la", "el", "los", "las", "en", "y", "a", "del"}
        self.strong_types = {
            "Event", "TouristAttraction", "Museum", "Monument", "Castle", "Alcazar",
            "Church", "Cathedral", "Basilica", "Chapel", "Monastery", "Abbey", "Convent",
            "Square", "Route", "AccommodationEstablishment", "FoodEstablishment",
            "TransportInfrastructure", "CultureCenter", "ExhibitionHall", "TownHall",
            "BullRing", "SportsCenter", "Stadium",
        }
        self.mid_types = {
            "Place", "Organization", "LocalBusiness", "Service", "TourismService",
            "PublicService", "PublicSpace", "ReligiousSite", "NaturalResource",
            "TourismDestination", "Accommodation", "RetailAndFashion", "SportFacility",
            "DestinationExperience",
        }
        self.editorial_markers = {
            "descubre", "sumérgete", "sumergite", "vive", "experiencia única",
            "no te pierdas", "te sorprenderá", "te sorprendera",
        }
        self.ui_noise_markers = {
            "todos los derechos reservados", "ir al contenido", "reserva tu",
            "convention bureau", "área profesional", "area profesional",
            "ver todas las noticias", "newsletter", "suscríbete", "apúntate",
        }

    def _normalize(self, text: str) -> str:
        text = (text or "").lower().strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _tokenize(self, text: str) -> List[str]:
        text = self._normalize(text)
        return [t for t in re.split(r"[^\wáéíóúñü]+", text) if t]

    def _slug_tokens(self, url: str) -> List[str]:
        try:
            path = urlparse(url or "").path.lower()
        except Exception:
            return []
        return [t for t in re.split(r"[^\w]+", path) if t]

    def _clean_text(self, text: str) -> str:
        text = (text or "").strip()
        return re.sub(r"\s+", " ", text)

    def _as_list(self, value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(v).strip() for v in value if str(v).strip()]
        value = str(value).strip()
        return [value] if value else []

    def _primary_label(self, entity: Dict[str, Any]) -> str:
        return entity.get("label") or entity.get("entity_name") or entity.get("entity") or entity.get("name") or ""

    def _score_name(self, label: str):
        tokens = self._tokenize(label)
        score = 0.0
        flags: List[str] = []
        if not tokens:
            return -3.0, ["empty_name"]
        if 2 <= len(tokens) <= 8:
            score += 2.0
        elif len(tokens) == 1:
            score -= 1.0
            flags.append("too_generic_name")
        elif len(tokens) > 12:
            score -= 1.0
            flags.append("too_long_name")
        meaningful = [t for t in tokens if t not in self.stop_tokens]
        if len(meaningful) >= 2:
            score += 1.0
        else:
            score -= 0.5
            flags.append("low_semantic_density")
        low = self._normalize(label)
        if any(m in low for m in self.ui_noise_markers):
            score -= 3.0
            flags.append("ui_noise")
        return score, flags

    def _score_description(self, short_desc: str, long_desc: str):
        score = 0.0
        flags: List[str] = []
        short_desc = self._clean_text(short_desc)
        long_desc = self._clean_text(long_desc)
        if short_desc:
            score += 0.75
        if long_desc:
            score += 1.5 if len(long_desc) > 80 else 0.75
        if not short_desc and not long_desc:
            score -= 1.0
            flags.append("no_description")
        low = long_desc.lower()
        if any(x in low for x in self.editorial_markers):
            score -= 0.5
            flags.append("editorial_text")
        return score, flags

    def _score_urls(self, label: str, related_urls: List[str], page_url: str = ""):
        score = 0.0
        flags: List[str] = []
        tokens = [t for t in self._tokenize(label) if len(t) > 3]
        urls = [u for u in (related_urls or []) if u]
        if page_url:
            urls.append(page_url)
        if not urls:
            return 0.0, ["no_related_urls"]
        match_count = 0
        for u in urls:
            slug_tokens = self._slug_tokens(u)
            if any(t in slug_tokens for t in tokens):
                match_count += 1
        if match_count > 0:
            score += min(2.5, 1.0 + match_count * 0.5)
        else:
            score -= 0.5
            flags.append("low_url_affinity")
        if len(urls) > 5 and match_count <= 1:
            score -= 0.5
            flags.append("noisy_urls")
        return score, flags

    def _score_properties(self, entity: Dict[str, Any]):
        score = 0.0
        flags: List[str] = []
        if entity.get("url") or entity.get("sourceUrl"):
            score += 0.75
        coords = entity.get("coordinates") or {}
        if isinstance(coords, dict) and coords.get("lat") is not None and coords.get("lng") is not None:
            score += 1.0
        if entity.get("address"):
            score += 0.75
        if entity.get("phone"):
            score += 0.5
        if entity.get("email"):
            score += 0.25
        if entity.get("image") or entity.get("mainImage"):
            score += 0.5
        if entity.get("schedule") or entity.get("openingHours"):
            score += 0.5
        return score, flags

    def _score_type(self, types):
        score = 0.0
        flags: List[str] = []
        types = self._as_list(types)
        if not types:
            return -0.5, ["no_type"]
        strong_hits = [t for t in types if t in self.strong_types]
        mid_hits = [t for t in types if t in self.mid_types]
        if strong_hits:
            score += 2.0
        elif mid_hits:
            score += 1.0
        else:
            flags.append("weak_type")
        if len(types) >= 2:
            score += 0.5
        return score, flags

    def _score_type_consistency(self, entity: Dict[str, Any]):
        score = 0.0
        flags: List[str] = []
        types = self._as_list(entity.get("type") or entity.get("types"))
        entity_class = str(entity.get("class", "")).strip()
        if not types and not entity_class:
            return -0.5, ["missing_class_and_type"]
        if entity_class and types:
            if entity_class in types:
                score += 1.0
            else:
                flags.append("class_not_in_types")
        if entity_class == "Concept":
            props = {k for k, v in entity.items() if v not in (None, "", [], {}, ())}
            if props.intersection({"address", "phone", "coordinates", "schedule", "openingHours"}):
                score -= 2.0
                flags.append("concept_with_operational_properties")
        return score, flags

    def _score_page_centrality(self, entity: Dict[str, Any], page_signals: Optional[Dict[str, Any]] = None):
        score = 0.0
        flags: List[str] = []
        page_signals = page_signals or {}
        label = self._normalize(self._primary_label(entity))
        h1 = self._normalize(page_signals.get("h1") or "")
        title = self._normalize(page_signals.get("title") or "")
        slug = self._normalize(page_signals.get("slug") or "")
        if label and h1 and (label in h1 or h1 in label):
            score += 2.0
        if label and title and (label in title or title in label):
            score += 1.0
        if label and slug and any(tok in slug for tok in self._tokenize(label) if len(tok) > 3):
            score += 1.0
        return score, flags

    def evaluate(self, entity: Dict[str, Any], page_url: str = "", page_signals: Optional[Dict[str, Any]] = None):
        label = self._primary_label(entity)
        short_desc = entity.get("short_description", "")
        long_desc = entity.get("long_description", "")
        related_urls = entity.get("relatedUrls", [])
        types = entity.get("type") or entity.get("types") or []
        total_score = 0.0
        flags: List[str] = []
        scorers = [
            lambda: self._score_name(label),
            lambda: self._score_description(short_desc, long_desc),
            lambda: self._score_urls(label, related_urls, page_url=page_url),
            lambda: self._score_properties(entity),
            lambda: self._score_type(types),
            lambda: self._score_type_consistency(entity),
            lambda: self._score_page_centrality(entity, page_signals=page_signals),
        ]
        for fn in scorers:
            s, f = fn()
            total_score += s
            flags.extend(f)
        total_score = max(0.0, min(10.0, round(total_score, 2)))
        if total_score >= 5.0:
            decision = "promote"
        elif total_score >= 2.0:
            decision = "review"
        else:
            decision = "discard"
        return {"score": total_score, "flags": sorted(set(flags)), "decision": decision}
