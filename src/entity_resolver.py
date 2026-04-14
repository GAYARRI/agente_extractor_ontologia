from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any, Dict, List, Set


class EntityResolver:
    SPECIFIC_CLASS_PRIORITY = {
        "Alcazar": 100,
        "Cathedral": 98,
        "Basilica": 96,
        "Chapel": 95,
        "Church": 94,
        "Castle": 93,
        "ArcheologicalSite": 92,
        "Bullring": 91,
        "TownHall": 90,
        "Stadium": 89,
        "Square": 88,
        "Museum": 87,
        "ExhibitionHall": 86,
        "CultureCenter": 85,
        "EducationalCenter": 84,
        "SportsCenter": 83,
        "SportFacility": 82,
        "TransportInfrastructure": 81,
        "FoodEstablishment": 80,
        "AccommodationEstablishment": 79,
        "Accommodation": 78,
        "TourismService": 77,
        "PublicService": 76,
        "EventOrganisationCompany": 75,
        "Event": 70,
        "Person": 65,
        "Route": 60,
        "Monument": 58,
        "TouristAttraction": 30,
        "TouristAttractionSite": 29,
        "TourismDestination": 20,
        "Place": 15,
        "Organization": 10,
        "LocalBusiness": 9,
        "Thing": 1,
        "Concept": 0,
    }

    def __init__(
        self,
        merge_threshold: float = 0.75,
        weak_variant_threshold: float = 0.92,
        min_name_len_for_direct_match: int = 4,
    ) -> None:
        self.merge_threshold = merge_threshold
        self.weak_variant_threshold = weak_variant_threshold
        self.min_name_len_for_direct_match = min_name_len_for_direct_match

    # =========================
    # API principal
    # =========================
    def deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not entities:
            return []

        enriched = [self._prepare_entity(e) for e in entities if isinstance(e, dict)]

        merged_groups: List[Dict[str, Any]] = []

        for entity in enriched:
            matched_index = None
            best_score = -1.0

            for i, existing in enumerate(merged_groups):
                score = self.entity_match_score(existing, entity)
                if score > best_score:
                    best_score = score
                    matched_index = i

            if matched_index is not None and best_score >= self.merge_threshold:
                merged_groups[matched_index] = self.merge_entities(
                    merged_groups[matched_index],
                    entity
                )
            else:
                merged_groups.append(entity)

        merged_groups = self._remove_weak_variants(merged_groups)
        merged_groups = [self._cleanup_entity(e) for e in merged_groups]

        return merged_groups

    # =========================
    # Preparación
    # =========================
    def _prepare_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        e = deepcopy(entity)

        primary_name = self._get_best_name(e)
        e["_primary_name"] = primary_name
        e["_canonical_name"] = self.canonicalize(primary_name)
        e["_aliases"] = sorted(self.extract_aliases(e))
        e["_canonical_aliases"] = sorted({self.canonicalize(a) for a in e["_aliases"] if a})
        e["_normalized_class"] = self.normalize_class_name(e.get("class") or e.get("type"))
        e["_source_url"] = e.get("sourceUrl") or e.get("url") or ""
        e["_wikidata_id"] = e.get("wikidata_id") or e.get("wikidataId") or self._extract_wikidata_from_properties(e)

        return e

    def _cleanup_entity(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        e = deepcopy(entity)
        for k in [
            "_primary_name",
            "_canonical_name",
            "_aliases",
            "_canonical_aliases",
            "_normalized_class",
            "_source_url",
            "_wikidata_id",
        ]:
            e.pop(k, None)
        return e

    # =========================
    # Normalización
    # =========================
    def canonicalize(self, text: str) -> str:
        if not text:
            return ""

        text = str(text).strip().lower()
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        text = re.sub(r"[«»\"'`´]", " ", text)
        text = re.sub(r"\b(la|el|los|las|un|una|de|del|al)\b", " ", text)
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def normalize_class_name(self, value: Any) -> str | None:
        if not value:
            return None

        if isinstance(value, list):
            if not value:
                return None
            value = value[0]

        value = str(value).strip()

        if "#" in value:
            value = value.split("#")[-1]
        elif "/" in value:
            value = value.rstrip("/").split("/")[-1]

        return value or None

    def class_priority(self, cls: str | None) -> int:
        if not cls:
            return 0
        return self.SPECIFIC_CLASS_PRIORITY.get(cls, 0)

    def extract_aliases(self, entity: Dict[str, Any]) -> Set[str]:
        aliases: Set[str] = set()

        for key in ["entity", "entity_name", "label", "name"]:
            val = entity.get(key)
            if isinstance(val, str) and val.strip():
                aliases.add(val.strip())

        wikidata_label = self._extract_label_from_properties(entity)
        if wikidata_label:
            aliases.add(wikidata_label)

        primary = self._get_best_name(entity)
        if primary:
            aliases.add(primary)

        generated = set()
        for alias in list(aliases):
            alias = alias.strip()
            if not alias:
                continue

            generated.add(alias)
            generated.add(self._remove_initial_article(alias))
            generated.add(alias.replace("’", "'"))

        aliases |= {a for a in generated if a and a.strip()}
        return aliases

    # =========================
    # Matching
    # =========================
    def entity_match_score(self, e1: Dict[str, Any], e2: Dict[str, Any]) -> float:
        score = 0.0

        wikidata1 = e1.get("_wikidata_id")
        wikidata2 = e2.get("_wikidata_id")

        if wikidata1 and wikidata2:
            if wikidata1 == wikidata2:
                return 1.0
            score -= 0.40

        c1 = e1.get("_canonical_name", "")
        c2 = e2.get("_canonical_name", "")

        if c1 and c2 and c1 == c2:
            score += 0.45

        alias_overlap = self.alias_overlap_score(e1, e2)
        score += 0.25 * alias_overlap

        fuzzy = self.fuzzy_name_similarity(
            e1.get("_primary_name", ""),
            e2.get("_primary_name", "")
        )
        score += 0.20 * fuzzy

        token_overlap = self.token_overlap_score(c1, c2)
        score += 0.10 * token_overlap

        if self.compatible_types(e1, e2):
            score += 0.10
        else:
            score -= 0.20

        if e1.get("_source_url") and e1.get("_source_url") == e2.get("_source_url"):
            score += 0.05

        if self.same_main_image(e1, e2):
            score += 0.05

        desc_sim = self.description_similarity(e1, e2)
        score += 0.05 * desc_sim

        return max(0.0, min(1.0, score))

    def alias_overlap_score(self, e1: Dict[str, Any], e2: Dict[str, Any]) -> float:
        a1 = set(e1.get("_canonical_aliases", []))
        a2 = set(e2.get("_canonical_aliases", []))

        if not a1 or not a2:
            return 0.0

        inter = len(a1 & a2)
        union = len(a1 | a2)
        return inter / union if union else 0.0

    def token_overlap_score(self, c1: str, c2: str) -> float:
        if not c1 or not c2:
            return 0.0

        t1 = set(c1.split())
        t2 = set(c2.split())

        if not t1 or not t2:
            return 0.0

        return len(t1 & t2) / len(t1 | t2)

    def fuzzy_name_similarity(self, n1: str, n2: str) -> float:
        if not n1 or not n2:
            return 0.0

        c1 = self.canonicalize(n1)
        c2 = self.canonicalize(n2)

        if not c1 or not c2:
            return 0.0

        return SequenceMatcher(None, c1, c2).ratio()

    def compatible_types(self, e1: Dict[str, Any], e2: Dict[str, Any]) -> bool:
        t1 = e1.get("_normalized_class")
        t2 = e2.get("_normalized_class")

        if not t1 or not t2:
            return True

        if t1 == t2:
            return True

        compatibility = {
            "Person": {"Person"},
            "Place": {
                "Place", "TouristAttraction", "TouristAttractionSite", "Square",
                "TownHall", "Castle", "Church", "Chapel", "Basilica", "Cathedral",
                "Museum", "ArcheologicalSite", "Bullring", "Monument", "Stadium",
                "CultureCenter", "ExhibitionHall", "TransportInfrastructure"
            },
            "TouristAttraction": {
                "TouristAttraction", "Place", "TouristAttractionSite", "Museum",
                "Castle", "Church", "Chapel", "Basilica", "Cathedral",
                "ArcheologicalSite", "Bullring", "Monument", "CultureCenter",
                "ExhibitionHall", "TownHall", "Square", "Stadium", "Alcazar"
            },
            "TouristAttractionSite": {
                "TouristAttraction", "Place", "TouristAttractionSite", "Museum",
                "Castle", "Church", "Chapel", "Basilica", "Cathedral",
                "ArcheologicalSite", "Bullring", "Monument", "CultureCenter",
                "ExhibitionHall", "TownHall", "Square", "Stadium", "Alcazar"
            },
            "TourismDestination": {
                "TourismDestination", "Place", "TouristAttraction", "TouristAttractionSite",
                "Square", "Monument", "Museum"
            },
            "Event": {"Event"},
            "Organization": {"Organization", "LocalBusiness", "EventOrganisationCompany"},
            "LocalBusiness": {"Organization", "LocalBusiness", "EventOrganisationCompany"},
            "EventOrganisationCompany": {"Organization", "LocalBusiness", "EventOrganisationCompany"},
            "Concept": {"Concept"},
        }

        allowed = compatibility.get(t1, {t1})
        if t2 in allowed:
            return True

        # compatibilidad simétrica
        allowed_rev = compatibility.get(t2, {t2})
        return t1 in allowed_rev

    def same_main_image(self, e1: Dict[str, Any], e2: Dict[str, Any]) -> bool:
        img1 = self._extract_image(e1)
        img2 = self._extract_image(e2)
        return bool(img1 and img2 and img1 == img2)

    def description_similarity(self, e1: Dict[str, Any], e2: Dict[str, Any]) -> float:
        d1 = (
            e1.get("description")
            or e1.get("long_description")
            or e1.get("short_description")
            or ""
        ).strip()
        d2 = (
            e2.get("description")
            or e2.get("long_description")
            or e2.get("short_description")
            or ""
        ).strip()

        if not d1 or not d2:
            return 0.0

        c1 = self.canonicalize(d1[:300])
        c2 = self.canonicalize(d2[:300])

        if not c1 or not c2:
            return 0.0

        return SequenceMatcher(None, c1, c2).ratio()

    # =========================
    # Merge
    # =========================
    def merge_entities(self, e1: Dict[str, Any], e2: Dict[str, Any]) -> Dict[str, Any]:
        merged = deepcopy(e1)

        best_name = self.choose_best_name(e1, e2)
        merged["entity"] = best_name
        merged["entity_name"] = best_name
        merged["name"] = best_name
        merged["label"] = best_name

        merged["class"] = self.choose_best_class(e1, e2)
        merged["type"] = self.merge_types(e1, e2)

        merged["score"] = max(e1.get("score", 0), e2.get("score", 0))
        merged["verisimilitude_score"] = max(
            e1.get("verisimilitude_score", 0),
            e2.get("verisimilitude_score", 0),
        )

        merged["short_description"] = self.choose_best_text(
            e1.get("short_description", ""),
            e2.get("short_description", "")
        )
        merged["long_description"] = self.choose_best_text(
            e1.get("long_description", ""),
            e2.get("long_description", "")
        )
        merged["description"] = self.choose_best_text(
            e1.get("description", ""),
            e2.get("description", "")
        )

        merged["wikidata_id"] = (
            e1.get("_wikidata_id")
            or e2.get("_wikidata_id")
            or e1.get("wikidata_id")
            or e2.get("wikidata_id")
        )

        merged["url"] = e1.get("url") or e2.get("url")
        merged["sourceUrl"] = e1.get("sourceUrl") or e2.get("sourceUrl")

        merged["relatedUrls"] = sorted(set(
            (e1.get("relatedUrls") or []) + (e2.get("relatedUrls") or [])
        ))

        merged["image"] = self.choose_best_image(e1, e2, field="image")
        merged["mainImage"] = self.choose_best_image(e1, e2, field="mainImage")

        merged["address"] = self.choose_best_text(e1.get("address", ""), e2.get("address", ""))
        merged["phone"] = e1.get("phone") or e2.get("phone") or ""
        merged["email"] = e1.get("email") or e2.get("email") or ""

        merged["coordinates"] = self.choose_best_coordinates(
            e1.get("coordinates"),
            e2.get("coordinates")
        )

        merged["properties"] = self.merge_properties(
            e1.get("properties") or {},
            e2.get("properties") or {}
        )

        aliases = set(e1.get("_aliases", [])) | set(e2.get("_aliases", []))
        merged["_aliases"] = sorted(aliases)
        merged["_canonical_aliases"] = sorted({self.canonicalize(a) for a in aliases if a})

        merged["_primary_name"] = best_name
        merged["_canonical_name"] = self.canonicalize(best_name)
        merged["_normalized_class"] = self.normalize_class_name(merged.get("class") or merged.get("type"))
        merged["_source_url"] = merged.get("sourceUrl") or merged.get("url") or ""
        merged["_wikidata_id"] = merged.get("wikidata_id") or self._extract_wikidata_from_properties(merged)

        return merged

    def choose_best_name(self, e1: Dict[str, Any], e2: Dict[str, Any]) -> str:
        candidates = [
            self._get_best_name(e1),
            self._get_best_name(e2),
            self._extract_label_from_properties(e1),
            self._extract_label_from_properties(e2),
        ]
        candidates = [c for c in candidates if c and c.strip()]

        if not candidates:
            return ""

        def score_name(name: str) -> tuple[int, int, int]:
            canonical = self.canonicalize(name)
            tokens = canonical.split()

            specific_boost = 0
            if any(term in canonical for term in [
                "alcazar", "catedral", "basilica", "capilla", "iglesia", "castillo",
                "plaza", "ayuntamiento", "estadio", "museo", "festival", "concierto"
            ]):
                specific_boost = 1

            return (specific_boost, len(tokens), len(name))

        return sorted(candidates, key=score_name, reverse=True)[0]

    def choose_best_class(self, e1: Dict[str, Any], e2: Dict[str, Any]) -> Any:
        c1 = self.normalize_class_name(e1.get("class") or e1.get("type"))
        c2 = self.normalize_class_name(e2.get("class") or e2.get("type"))

        if c1 and c2:
            return c1 if self.class_priority(c1) >= self.class_priority(c2) else c2

        return c1 or c2 or e1.get("class") or e2.get("class")

    def merge_types(self, e1: Dict[str, Any], e2: Dict[str, Any]) -> List[Any]:
        t1 = e1.get("type", [])
        t2 = e2.get("type", [])

        if not isinstance(t1, list):
            t1 = [t1] if t1 else []
        if not isinstance(t2, list):
            t2 = [t2] if t2 else []

        merged = []
        seen = set()
        for t in t1 + t2:
            key = str(t)
            if key not in seen:
                seen.add(key)
                merged.append(t)
        return merged

    def merge_properties(self, p1: Dict[str, Any], p2: Dict[str, Any]) -> Dict[str, Any]:
        merged = deepcopy(p1)

        for key, val2 in p2.items():
            val1 = merged.get(key)

            if not val1 and val2:
                merged[key] = val2
                continue

            if isinstance(val1, list) and isinstance(val2, list):
                merged[key] = list(dict.fromkeys(val1 + val2))
                continue

            if isinstance(val1, dict) and isinstance(val2, dict):
                merged[key] = {**val1, **val2}
                continue

            if isinstance(val1, str) and isinstance(val2, str):
                merged[key] = self.choose_best_text(val1, val2)
                continue

        return merged

    # =========================
    # Poda de variantes débiles
    # =========================
    def _remove_weak_variants(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        kept = []

        for i, entity in enumerate(entities):
            is_weak = False
            for j, other in enumerate(entities):
                if i == j:
                    continue
                if self.is_weaker_name_variant(entity, other):
                    is_weak = True
                    break
            if not is_weak:
                kept.append(entity)

        return kept

    def is_weaker_name_variant(self, short_e: Dict[str, Any], long_e: Dict[str, Any]) -> bool:
        n1 = short_e.get("_canonical_name", "")
        n2 = long_e.get("_canonical_name", "")

        if not n1 or not n2 or n1 == n2:
            return False

        t1 = set(n1.split())
        t2 = set(n2.split())

        if not t1 or not t2:
            return False

        if len(t1) > len(t2):
            return False

        if not t1.issubset(t2):
            return False

        if not self.compatible_types(short_e, long_e):
            return False

        if short_e.get("_wikidata_id") and long_e.get("_wikidata_id"):
            if short_e["_wikidata_id"] != long_e["_wikidata_id"]:
                return False

        short_cls = short_e.get("_normalized_class")
        long_cls = long_e.get("_normalized_class")
        if self.class_priority(long_cls) < self.class_priority(short_cls):
            return False

        # variante más débil: pocos tokens y el otro nombre lo contiene
        return (
            len(t1) <= 3
            and len(n1) < len(n2)
            and self.fuzzy_name_similarity(
                short_e.get("_primary_name", ""),
                long_e.get("_primary_name", "")
            ) >= 0.45
        )

    # =========================
    # Helpers
    # =========================
    def choose_best_text(self, t1: str, t2: str) -> str:
        t1 = (t1 or "").strip()
        t2 = (t2 or "").strip()

        if not t1:
            return t2
        if not t2:
            return t1

        return t1 if len(t1) >= len(t2) else t2

    def choose_best_image(self, e1: Dict[str, Any], e2: Dict[str, Any], field: str) -> str:
        v1 = e1.get(field) or (e1.get("properties") or {}).get(field, "")
        v2 = e2.get(field) or (e2.get("properties") or {}).get(field, "")

        if v1 and not v2:
            return v1
        if v2 and not v1:
            return v2
        if len(str(v1)) >= len(str(v2)):
            return v1 or ""
        return v2 or ""

    def choose_best_coordinates(self, c1: Any, c2: Any) -> Dict[str, Any]:
        c1 = c1 or {}
        c2 = c2 or {}

        def valid(c: Dict[str, Any]) -> bool:
            return c.get("lat") is not None and c.get("lng") is not None

        if valid(c1):
            return c1
        if valid(c2):
            return c2
        return c1 or c2 or {"lat": None, "lng": None}

    def _get_best_name(self, entity: Dict[str, Any]) -> str:
        for key in ["name", "entity_name", "entity", "label"]:
            val = entity.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return ""

    def _extract_label_from_properties(self, entity: Dict[str, Any]) -> str:
        props = entity.get("properties") or {}
        val = props.get("label")
        return val.strip() if isinstance(val, str) and val.strip() else ""

    def _extract_wikidata_from_properties(self, entity: Dict[str, Any]) -> str:
        props = entity.get("properties") or {}
        val = props.get("wikidata_id") or props.get("wikidataId")
        return val.strip() if isinstance(val, str) and val.strip() else ""

    def _extract_image(self, entity: Dict[str, Any]) -> str:
        return (
            entity.get("mainImage")
            or entity.get("image")
            or (entity.get("properties") or {}).get("mainImage")
            or (entity.get("properties") or {}).get("image")
            or ""
        )

    def _remove_initial_article(self, text: str) -> str:
        text = text.strip()
        return re.sub(r"^(la|el|los|las)\s+", "", text, flags=re.IGNORECASE).strip()