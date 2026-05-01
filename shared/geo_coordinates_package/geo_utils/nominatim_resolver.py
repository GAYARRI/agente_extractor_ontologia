import hashlib
import json
import os
import re
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import requests


class HybridGeoResolver:
    WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
    WIKIDATA_ENTITYDATA_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"

    def __init__(
        self,
        cache_path: str = "cache/geo_resolver_cache.json",
        user_agent: str = "geo-coordinates-package/1.0",
        min_delay_seconds: float = 1.1,
        timeout_seconds: int = 15,
        countrycodes: str = "es",
        default_city: str = "Madrid",
    ):
        self.cache_path = cache_path
        self.user_agent = user_agent
        self.min_delay_seconds = min_delay_seconds
        self.timeout_seconds = timeout_seconds
        self.countrycodes = countrycodes
        self.default_city = default_city
        self._last_call_ts = 0.0

        cache_dir = os.path.dirname(self.cache_path)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if not os.path.exists(self.cache_path):
            return {}
        try:
            with open(self.cache_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self) -> None:
        tmp_path = f"{self.cache_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as file:
            json.dump(self.cache, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.cache_path)

    def _normalize_query(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"^\d+[_\-\.\)]\s*", "", text)
        return text.strip(" ,;:")

    def _normalize_ascii(self, text: str) -> str:
        value = self._normalize_query(text).lower()
        value = unicodedata.normalize("NFD", value)
        return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")

    def _cache_key(self, resolver: str, query: str) -> str:
        raw = f"{resolver}::{self._normalize_query(query)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _respect_rate_limit(self) -> None:
        elapsed = time.time() - self._last_call_ts
        if elapsed < self.min_delay_seconds:
            time.sleep(self.min_delay_seconds - elapsed)

    def _get_json(self, url: str, params: Optional[dict] = None) -> Any:
        self._respect_rate_limit()
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": self.user_agent, "Accept-Language": "es"},
            timeout=self.timeout_seconds,
        )
        self._last_call_ts = time.time()
        response.raise_for_status()
        return response.json()

    def _build_query_candidates(self, entity_name: str, address: str = "", entity_class: str = "") -> List[str]:
        entity_name = self._normalize_query(entity_name)
        address = self._normalize_query(address)
        candidates: List[str] = []
        if address:
            candidates.append(f"{entity_name}, {address}, {self.default_city}, España")
        candidates.append(f"{entity_name}, {self.default_city}, España")
        candidates.append(entity_name)

        if entity_class == "Place":
            candidates.append(f"{entity_name}, lugar, {self.default_city}, España")
        elif entity_class == "Organization":
            candidates.append(f"{entity_name}, edificio, {self.default_city}, España")

        out = []
        seen = set()
        for query in candidates:
            key = query.lower().strip()
            if key and key not in seen:
                seen.add(key)
                out.append(query)
        return out

    def _parse_wikidata_coordinate(self, claim_obj: dict) -> Tuple[Optional[float], Optional[float]]:
        try:
            mainsnak = claim_obj.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            lat = value.get("latitude")
            lng = value.get("longitude")
            if lat is None or lng is None:
                return None, None
            return float(lat), float(lng)
        except Exception:
            return None, None

    def _wikidata_search_candidates(self, query: str) -> List[dict]:
        data = self._get_json(
            self.WIKIDATA_SEARCH_URL,
            params={
                "action": "wbsearchentities",
                "search": query,
                "language": "es",
                "uselang": "es",
                "format": "json",
                "type": "item",
                "limit": 5,
            },
        )
        return data.get("search", []) if isinstance(data, dict) else []

    def _wikidata_entity_data(self, qid: str) -> dict:
        data = self._get_json(self.WIKIDATA_ENTITYDATA_URL.format(qid=qid))
        return data if isinstance(data, dict) else {}

    def _score_wikidata_candidate(self, candidate: dict, entity_name: str) -> float:
        score = 0.0
        entity_name_l = (entity_name or "").lower()
        label = str(candidate.get("label", "")).lower()
        desc = str(candidate.get("description", "")).lower()
        if entity_name_l and entity_name_l in label:
            score += 5.0
        if "españa" in desc or "espana" in desc:
            score += 1.0
        if candidate.get("id", "").startswith("Q"):
            score += 0.2
        return score

    def _resolve_with_wikidata(self, entity_name: str, address: str = "", entity_class: str = "") -> Dict[str, Any]:
        for query in self._build_query_candidates(entity_name, address, entity_class):
            cache_key = self._cache_key("wikidata", query)
            if cache_key in self.cache and self.cache[cache_key].get("lat") is not None:
                return self.cache[cache_key]
            try:
                candidates = self._wikidata_search_candidates(query)
                if not candidates:
                    self.cache[cache_key] = {"lat": None, "lng": None, "source": "wikidata", "query": query}
                    self._save_cache()
                    continue

                scored = sorted(
                    ((self._score_wikidata_candidate(candidate, entity_name), candidate) for candidate in candidates),
                    key=lambda item: item[0],
                    reverse=True,
                )
                for best_score, best in scored:
                    if best_score < 3.0:
                        continue
                    qid = best.get("id")
                    if not qid:
                        continue
                    entity_data = self._wikidata_entity_data(qid)
                    item = entity_data.get("entities", {}).get(qid, {})
                    for claim in item.get("claims", {}).get("P625", []):
                        lat, lng = self._parse_wikidata_coordinate(claim)
                        if lat is None or lng is None:
                            continue
                        result = {
                            "lat": lat,
                            "lng": lng,
                            "source": "wikidata",
                            "query": query,
                            "wikidata_id": qid,
                            "label": best.get("label", ""),
                            "description": best.get("description", ""),
                        }
                        self.cache[cache_key] = result
                        self._save_cache()
                        return result
            except Exception:
                pass

            self.cache[cache_key] = {"lat": None, "lng": None, "source": "wikidata", "query": query}
            self._save_cache()

        return {"lat": None, "lng": None, "source": "wikidata"}

    def _nominatim_search(self, query: str) -> List[dict]:
        data = self._get_json(
            self.NOMINATIM_SEARCH_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 5,
                "addressdetails": 1,
                "countrycodes": self.countrycodes,
            },
        )
        return data if isinstance(data, list) else []

    def _score_nominatim_result(self, result: dict, entity_name: str, entity_class: str = "") -> float:
        score = 0.0
        entity_name_l = (entity_name or "").lower()
        display_name = str(result.get("display_name", "")).lower()
        category = str(result.get("category", "")).lower()
        result_type = str(result.get("type", "")).lower()
        importance = float(result.get("importance", 0.0) or 0.0)
        if entity_name_l and entity_name_l in display_name:
            score += 5.0
        score += importance
        if entity_class == "Place" and category in {"tourism", "amenity", "historic", "leisure", "place", "boundary"}:
            score += 2.0
        if entity_class == "Organization" and result_type in {"university", "college", "school"}:
            score += 2.0
        return score

    def _resolve_with_nominatim(self, entity_name: str, address: str = "", entity_class: str = "") -> Dict[str, Any]:
        for query in self._build_query_candidates(entity_name, address, entity_class):
            cache_key = self._cache_key("nominatim", query)
            if cache_key in self.cache and self.cache[cache_key].get("lat") is not None:
                return self.cache[cache_key]
            try:
                results = self._nominatim_search(query)
                scored = []
                for result in results:
                    lat = result.get("lat")
                    lng = result.get("lon")
                    if lat is None or lng is None:
                        continue
                    scored.append((self._score_nominatim_result(result, entity_name, entity_class), result))
                scored.sort(key=lambda item: item[0], reverse=True)
                if scored and scored[0][0] >= 2.0:
                    best = scored[0][1]
                    result = {
                        "lat": float(best["lat"]),
                        "lng": float(best["lon"]),
                        "source": "nominatim",
                        "query": query,
                        "display_name": best.get("display_name", ""),
                    }
                    self.cache[cache_key] = result
                    self._save_cache()
                    return result
            except Exception:
                pass

            self.cache[cache_key] = {"lat": None, "lng": None, "source": "nominatim", "query": query}
            self._save_cache()

        return {"lat": None, "lng": None, "source": "nominatim"}

    def resolve(self, entity_name: str, address: str = "", source_url: str = "", entity_class: str = "") -> Dict[str, Any]:
        entity_name = self._normalize_query(entity_name)
        if not entity_name:
            return {"lat": None, "lng": None, "source": None}

        wikidata_result = self._resolve_with_wikidata(entity_name, address, entity_class)
        if wikidata_result.get("lat") is not None and wikidata_result.get("lng") is not None:
            return wikidata_result

        nominatim_result = self._resolve_with_nominatim(entity_name, address, entity_class)
        if nominatim_result.get("lat") is not None and nominatim_result.get("lng") is not None:
            return nominatim_result

        return {"lat": None, "lng": None, "source": None}
