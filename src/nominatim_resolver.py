import json
import os
import re
import time
import hashlib
from typing import Optional, Dict, Any, List, Tuple

import requests


class HybridGeoResolver:
    """
    Resolver híbrido:
    1) Wikidata primero
    2) Nominatim después
    3) Caché persistente en disco
    4) Rate limit simple
    """

    WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
    WIKIDATA_ENTITYDATA_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"

    def __init__(
        self,
        cache_path: str = "cache/geo_resolver_cache.json",
        user_agent: str = "agente-extractor-ontologia/1.0 (contacto: TU_EMAIL_AQUI)",
        min_delay_seconds: float = 1.1,
        timeout_seconds: int = 15,
        countrycodes: str = "es",
        default_city: str = "Sevilla",
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

    # -------------------------
    # caché
    # -------------------------
    def _load_cache(self) -> Dict[str, Any]:
        if not os.path.exists(self.cache_path):
            return {}

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_cache(self) -> None:
        tmp_path = f"{self.cache_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.cache_path)

    def _cache_key(self, resolver: str, query: str) -> str:
        raw = f"{resolver}::{self._normalize_query(query)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # -------------------------
    # utils
    # -------------------------
    def _normalize_query(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"^\d+[_\-\.\)]\s*", "", text)
        return text.strip(" ,;:")

    def _respect_rate_limit(self) -> None:
        elapsed = time.time() - self._last_call_ts
        if elapsed < self.min_delay_seconds:
            time.sleep(self.min_delay_seconds - elapsed)

    def _get_json(self, url: str, params: Optional[dict] = None) -> Any:
        self._respect_rate_limit()

        headers = {
            "User-Agent": self.user_agent,
            "Accept-Language": "es",
        }

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=self.timeout_seconds,
        )
        self._last_call_ts = time.time()
        response.raise_for_status()
        return response.json()

    def _build_query_candidates(
        self,
        entity_name: str,
        address: str = "",
        entity_class: str = "",
    ) -> List[str]:
        entity_name = self._normalize_query(entity_name)
        address = self._normalize_query(address)
        entity_class = (entity_class or "").strip()

        candidates = []

        if address:
            candidates.append(f"{entity_name}, {address}, {self.default_city}, España")

        candidates.append(f"{entity_name}, {self.default_city}, España")
        candidates.append(entity_name)

        if entity_class == "Person":
            candidates.append(f"{entity_name}, monumento, {self.default_city}, España")
        elif entity_class == "Place":
            candidates.append(f"{entity_name}, lugar, {self.default_city}, España")
        elif entity_class == "Organization":
            candidates.append(f"{entity_name}, universidad, {self.default_city}, España")
        elif entity_class == "Service":
            candidates.append(f"{entity_name}, servicio, {self.default_city}, España")

        out = []
        seen = set()
        for q in candidates:
            key = q.lower().strip()
            if key and key not in seen:
                seen.add(key)
                out.append(q)

        return out

    def _parse_wikidata_coordinate(self, claim_obj: dict) -> Tuple[Optional[float], Optional[float]]:
        """
        P625 -> globe-coordinate
        """
        try:
            mainsnak = claim_obj.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            lat = value.get("latitude")
            lon = value.get("longitude")
            if lat is None or lon is None:
                return None, None
            return float(lat), float(lon)
        except Exception:
            return None, None

    def _wikidata_search_candidates(self, query: str) -> List[dict]:
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "es",
            "uselang": "es",
            "format": "json",
            "type": "item",
            "limit": 5,
        }
        data = self._get_json(self.WIKIDATA_SEARCH_URL, params=params)
        return data.get("search", []) if isinstance(data, dict) else []

    def _wikidata_entity_data(self, qid: str) -> dict:
        url = self.WIKIDATA_ENTITYDATA_URL.format(qid=qid)
        data = self._get_json(url)
        return data if isinstance(data, dict) else {}

    def _score_wikidata_candidate(
        self,
        candidate: dict,
        entity_name: str,
        entity_class: str = "",
    ) -> float:
        score = 0.0
        entity_name_l = (entity_name or "").lower()

        label = str(candidate.get("label", "")).lower()
        desc = str(candidate.get("description", "")).lower()
        qid = str(candidate.get("id", ""))

        if entity_name_l and entity_name_l in label:
            score += 5.0

        if "sevilla" in label or "sevilla" in desc:
            score += 2.0
        if "andalucía" in desc or "andalucia" in desc:
            score += 1.0
        if "españa" in desc or "espana" in desc:
            score += 1.0

        if entity_class == "Organization":
            if any(x in desc for x in ["universidad", "institución educativa", "institucion educativa"]):
                score += 2.0
        elif entity_class == "Place":
            if any(x in desc for x in ["ciudad", "barrio", "plaza", "puente", "isla", "municipio"]):
                score += 2.0
        elif entity_class == "Service":
            if any(x in desc for x in ["servicio", "transporte", "bicicleta", "bicicletas"]):
                score += 1.5

        if qid.startswith("Q"):
            score += 0.2

        return score

    def _resolve_with_wikidata(
        self,
        entity_name: str,
        address: str = "",
        entity_class: str = "",
    ) -> Dict[str, Any]:
        queries = self._build_query_candidates(entity_name, address, entity_class)

        for query in queries:
            cache_key = self._cache_key("wikidata", query)
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if cached.get("lat") is not None and cached.get("lng") is not None:
                    return cached

            try:
                candidates = self._wikidata_search_candidates(query)
                if not candidates:
                    self.cache[cache_key] = {"lat": None, "lng": None, "source": "wikidata", "query": query}
                    self._save_cache()
                    continue

                scored = []
                for cand in candidates:
                    scored.append((self._score_wikidata_candidate(cand, entity_name, entity_class), cand))

                scored.sort(key=lambda x: x[0], reverse=True)

                for best_score, best in scored:
                    if best_score < 3.0:
                        continue

                    qid = best.get("id")
                    if not qid:
                        continue

                    entity_data = self._wikidata_entity_data(qid)
                    entities = entity_data.get("entities", {})
                    item = entities.get(qid, {})
                    claims = item.get("claims", {})

                    # P625 = coordinate location
                    p625_claims = claims.get("P625", [])
                    for claim in p625_claims:
                        lat, lng = self._parse_wikidata_coordinate(claim)
                        if lat is not None and lng is not None:
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

                self.cache[cache_key] = {"lat": None, "lng": None, "source": "wikidata", "query": query}
                self._save_cache()

            except Exception:
                self.cache[cache_key] = {"lat": None, "lng": None, "source": "wikidata", "query": query}
                self._save_cache()

        return {"lat": None, "lng": None, "source": "wikidata"}

    # -------------------------
    # Nominatim
    # -------------------------
    def _nominatim_search(self, query: str) -> List[dict]:
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": 5,
            "addressdetails": 1,
            "countrycodes": self.countrycodes,
        }
        data = self._get_json(self.NOMINATIM_SEARCH_URL, params=params)
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

        if "sevilla" in display_name:
            score += 2.0

        score += importance

        if entity_class == "Place":
            if category in {"tourism", "amenity", "historic", "leisure", "place", "boundary"}:
                score += 2.0

        elif entity_class == "Organization":
            if category in {"amenity", "building", "office"}:
                score += 1.5
            if result_type in {"university", "college", "school"}:
                score += 2.0

        elif entity_class == "Service":
            if category in {"amenity", "shop", "office"}:
                score += 1.0

        elif entity_class in {"Person", "Event", "Concept", "Thing"}:
            score -= 1.5

        return score

    def _resolve_with_nominatim(
        self,
        entity_name: str,
        address: str = "",
        entity_class: str = "",
    ) -> Dict[str, Any]:
        queries = self._build_query_candidates(entity_name, address, entity_class)

        for query in queries:
            cache_key = self._cache_key("nominatim", query)
            if cache_key in self.cache:
                cached = self.cache[cache_key]
                if cached.get("lat") is not None and cached.get("lng") is not None:
                    return cached

            try:
                results = self._nominatim_search(query)
                if not results:
                    self.cache[cache_key] = {"lat": None, "lng": None, "source": "nominatim", "query": query}
                    self._save_cache()
                    continue

                scored = []
                for r in results:
                    lat = r.get("lat")
                    lon = r.get("lon")
                    if lat is None or lon is None:
                        continue
                    scored.append((self._score_nominatim_result(r, entity_name, entity_class), r))

                scored.sort(key=lambda x: x[0], reverse=True)

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

                self.cache[cache_key] = {"lat": None, "lng": None, "source": "nominatim", "query": query}
                self._save_cache()

            except Exception:
                self.cache[cache_key] = {"lat": None, "lng": None, "source": "nominatim", "query": query}
                self._save_cache()

        return {"lat": None, "lng": None, "source": "nominatim"}

    # -------------------------
    # API pública
    # -------------------------
    def resolve(
        self,
        entity_name: str,
        address: str = "",
        source_url: str = "",
        entity_class: str = "",
    ) -> Dict[str, Any]:
        entity_name = self._normalize_query(entity_name)
        if not entity_name:
            return {"lat": None, "lng": None, "source": None}

        # 1) Wikidata
        wikidata_result = self._resolve_with_wikidata(
            entity_name=entity_name,
            address=address,
            entity_class=entity_class,
        )
        if wikidata_result.get("lat") is not None and wikidata_result.get("lng") is not None:
            return wikidata_result

        # 2) Nominatim
        nominatim_result = self._resolve_with_nominatim(
            entity_name=entity_name,
            address=address,
            entity_class=entity_class,
        )
        if nominatim_result.get("lat") is not None and nominatim_result.get("lng") is not None:
            return nominatim_result

        return {"lat": None, "lng": None, "source": None}
