# src/linking/wikidata_linker.py

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional
import requests

import requests


class WikidataLinker:
    """
    Vincula entidades textuales con ítems de Wikidata.

    Devuelve preferentemente el QID (por ejemplo, 'Q8717').
    También puede devolver metadatos internos en candidatos intermedios.
    """

    WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
    WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

    def __init__(
        self,
        language: str = "es",
        limit: int = 5,
        timeout: int = 15,
        min_score: float = 0.55,
    ) -> None:
        self.language = language
        self.limit = limit
        self.timeout = timeout
        self.min_score = min_score
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "TourismOntologyAgent/1.0 (contact: dev@example.com)"
            }
        )

    # -------------------------------------------------------------------------
    # API pública
    # -------------------------------------------------------------------------

    def link(
        self,
        entity_name: str,
        entity_class: Optional[str] = None,
        short_description: str = "",
        long_description: str = "",
        source_url: str = "",
        aliases: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Devuelve el wikidata_id (Qxxx) o None si no encuentra candidato fiable.
        """
        entity_name = self._safe_string(entity_name)
        entity_class = self._safe_string(entity_class)
        short_description = self._safe_string(short_description)
        long_description = self._safe_string(long_description)
        source_url = self._safe_string(source_url)
        aliases = aliases or [entity_name]

        print("\n=== DEBUG WIKIDATA INPUT ===")
        print(f"NAME: {entity_name}")
        print(f"CLASS: {entity_class or None}")
        print(f"ALIASES: {aliases}")

        if not entity_name:
            print("⚠️ Wikidata linker: entity_name vacío")
            return None

        mapped_class = self._map_class(entity_class, short_description, long_description)
        print(f"MAPPED CLASS: {mapped_class}")

        candidates = self._search_wikidata(entity_name)

        # Intento adicional sin acentos si no hay nada
        if not candidates:
            normalized_query = self._strip_accents(entity_name)
            if normalized_query != entity_name:
                candidates = self._search_wikidata(normalized_query)

        print(f"CANDIDATES for {entity_name}: {len(candidates)}")

        best_candidate: Optional[Dict[str, Any]] = None
        best_score = 0.0

        for candidate in candidates:
            qid = candidate.get("id", "")
            if not qid:
                continue

            entity_data = self._get_entity_data(qid)
            score = self._score_candidate(
                candidate=candidate,
                entity_data=entity_data,
                entity_name=entity_name,
                aliases=aliases,
                mapped_class=mapped_class,
                short_description=short_description,
                long_description=long_description,
                source_url=source_url,
            )

            candidate["_score"] = score

            if score > best_score:
                best_score = score
                best_candidate = candidate

        print(f"BEST SCORE: {best_score}")
        print(f"BEST CANDIDATE: {best_candidate.get('id') if best_candidate else None}")

        if best_candidate and best_score >= self.min_score:
            return best_candidate.get("id")

        return None


    def get_entity_data(self, qid: str) -> dict:
        if not qid:
            return {}

        url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"⚠️ get_entity_data request error: {e}")
            return {}

        try:
            entity = data["entities"][qid]
        except Exception:
            return {}

        result = {
            "wikidata_id": qid,
            "label": "",
            "description": "",
            "latitude": None,
            "longitude": None,
            "image": "",
        }

        labels = entity.get("labels", {})
        descriptions = entity.get("descriptions", {})
        claims = entity.get("claims", {})

        # label
        if "es" in labels:
            result["label"] = labels["es"].get("value", "")
        elif "en" in labels:
            result["label"] = labels["en"].get("value", "")

        # description
        if "es" in descriptions:
            result["description"] = descriptions["es"].get("value", "")
        elif "en" in descriptions:
            result["description"] = descriptions["en"].get("value", "")

        # coordenadas (P625)
        try:
            coord_claims = claims.get("P625", [])
            if coord_claims:
                coord = coord_claims[0]["mainsnak"]["datavalue"]["value"]
                result["latitude"] = coord.get("latitude")
                result["longitude"] = coord.get("longitude")
        except Exception:
            pass

        # imagen (P18)
        try:
            image_claims = claims.get("P18", [])
            if image_claims:
                result["image"] = image_claims[0]["mainsnak"]["datavalue"]["value"]
        except Exception:
            pass

        return result


    # -------------------------------------------------------------------------
    # Búsqueda y fetch
    # -------------------------------------------------------------------------

    def _search_wikidata(self, query: str) -> List[Dict[str, Any]]:
        query = self._safe_string(query)
        if not query:
            return []

        params = {
            "action": "wbsearchentities",
            "format": "json",
            "language": self.language,
            "uselang": self.language,
            "type": "item",
            "limit": self.limit,
            "search": query,
        }

        try:
            response = self.session.get(
                self.WIKIDATA_API_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("search", []) or []
        except Exception as e:
            print(f"⚠️ _search_wikidata request error: {e}")
            return []

    def _get_entity_data(self, qid: str) -> Dict[str, Any]:
        qid = self._safe_string(qid)
        if not qid:
            return {}

        url = self.WIKIDATA_ENTITY_URL.format(qid=qid)

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            return payload.get("entities", {}).get(qid, {}) or {}
        except Exception as e:
            print(f"⚠️ _get_entity_data request error for {qid}: {e}")
            return {}

    # -------------------------------------------------------------------------
    # Scoring
    # -------------------------------------------------------------------------

    def _score_candidate(
        self,
        candidate: Dict[str, Any],
        entity_data: Dict[str, Any],
        entity_name: str,
        aliases: List[str],
        mapped_class: str,
        short_description: str,
        long_description: str,
        source_url: str,
    ) -> float:
        score = 0.0

        candidate_label = self._extract_candidate_label(candidate, entity_data)
        candidate_desc = self._extract_candidate_description(candidate, entity_data)
        candidate_aliases = self._extract_candidate_aliases(candidate, entity_data)
        candidate_instance_of = self._extract_instance_of(entity_data)

        norm_entity = self._normalize_text(entity_name)
        norm_label = self._normalize_text(candidate_label)

        # Coincidencia exacta con label
        if norm_entity and norm_label == norm_entity:
            score += 0.45
        elif norm_entity and norm_entity in norm_label:
            score += 0.30

        # Coincidencia con aliases
        norm_aliases = {self._normalize_text(a) for a in aliases if self._safe_string(a)}
        norm_candidate_aliases = {
            self._normalize_text(a) for a in candidate_aliases if self._safe_string(a)
        }

        if norm_entity in norm_candidate_aliases:
            score += 0.20

        if norm_aliases.intersection(norm_candidate_aliases):
            score += 0.10

        # Similaridad textual simple con descripciones
        local_desc = self._normalize_text(f"{short_description} {long_description}")
        remote_desc = self._normalize_text(candidate_desc)

        if local_desc and remote_desc:
            overlap = self._token_overlap(local_desc, remote_desc)
            score += min(overlap * 0.25, 0.15)

        # Penalizar desambiguaciones
        if "desambigu" in remote_desc:
            score -= 0.40

        # Bonus por tipo compatible
        if self._is_type_compatible(mapped_class, candidate_instance_of, candidate_desc):
            score += 0.20

        # Bonus geográfico si la URL o el contexto sugiere Sevilla
        if "sevilla" in self._normalize_text(source_url):
            sevilla_hit = (
                "sevilla" in remote_desc
                or "sevilla" in norm_label
                or any("sevilla" in self._normalize_text(a) for a in candidate_aliases)
            )
            if sevilla_hit:
                score += 0.10

        # Acotar
        score = max(0.0, min(1.0, score))
        return score

    # -------------------------------------------------------------------------
    # Mapping de clases
    # -------------------------------------------------------------------------

    def _map_class(
        self,
        entity_class: Optional[str],
        short_description: str = "",
        long_description: str = "",
    ) -> str:
        """
        Reduce clases del pipeline a categorías útiles para Wikidata.
        """
        text = " ".join(
            [
                self._safe_string(entity_class),
                self._safe_string(short_description),
                self._safe_string(long_description),
            ]
        )
        norm = self._normalize_text(text)

        if any(k in norm for k in ["monument", "monumento", "iglesia", "catedral", "capilla"]):
            return "monument"

        if any(k in norm for k in ["museum", "museo", "touristattraction", "touristattraction"]):
            return "tourist_attraction"

        if any(k in norm for k in ["event", "evento", "festival", "feria", "semana santa"]):
            return "event"

        if any(k in norm for k in ["company", "empresa", "organization", "organizacion"]):
            return "organization"

        if any(
            k in norm
            for k in [
                "place",
                "location",
                "destination",
                "tourismdestination",
                "barrio",
                "ciudad",
                "zona",
                "district",
                "neighbourhood",
                "neighborhood",
            ]
        ):
            return "place"

        return "place"

    def _is_type_compatible(
        self,
        mapped_class: str,
        candidate_instance_of: List[str],
        candidate_desc: str,
    ) -> bool:
        haystack = self._normalize_text(" ".join(candidate_instance_of) + " " + candidate_desc)

        if mapped_class == "place":
            keys = [
                "city",
                "municipality",
                "human settlement",
                "neighbourhood",
                "neighborhood",
                "district",
                "barrio",
                "localidad",
                "ciudad",
                "quarter",
                "plaza",
                "island",
            ]
            return any(self._normalize_text(k) in haystack for k in keys)

        if mapped_class == "monument":
            keys = [
                "monument",
                "church",
                "cathedral",
                "chapel",
                "building",
                "heritage",
                "tourist attraction",
                "arquitect",
                "monumento",
            ]
            return any(self._normalize_text(k) in haystack for k in keys)

        if mapped_class == "tourist_attraction":
            keys = [
                "tourist attraction",
                "museum",
                "site",
                "visitor attraction",
                "museo",
                "atraccion",
            ]
            return any(self._normalize_text(k) in haystack for k in keys)

        if mapped_class == "event":
            keys = [
                "event",
                "festival",
                "celebration",
                "holiday",
                "festividad",
            ]
            return any(self._normalize_text(k) in haystack for k in keys)

        if mapped_class == "organization":
            keys = [
                "company",
                "organization",
                "business",
                "corporation",
                "empresa",
                "organizacion",
            ]
            return any(self._normalize_text(k) in haystack for k in keys)

        return False

    # -------------------------------------------------------------------------
    # Extractores de datos del candidato
    # -------------------------------------------------------------------------

    def _extract_candidate_label(self, candidate: Dict[str, Any], entity_data: Dict[str, Any]) -> str:
        label = self._safe_string(candidate.get("label"))
        if label:
            return label

        labels = entity_data.get("labels", {})
        if self.language in labels:
            return self._safe_string(labels[self.language].get("value"))
        if "en" in labels:
            return self._safe_string(labels["en"].get("value"))

        return ""

    def _extract_candidate_description(self, candidate: Dict[str, Any], entity_data: Dict[str, Any]) -> str:
        desc = self._safe_string(candidate.get("description"))
        if desc:
            return desc

        descriptions = entity_data.get("descriptions", {})
        if self.language in descriptions:
            return self._safe_string(descriptions[self.language].get("value"))
        if "en" in descriptions:
            return self._safe_string(descriptions["en"].get("value"))

        return ""

    def _extract_candidate_aliases(self, candidate: Dict[str, Any], entity_data: Dict[str, Any]) -> List[str]:
        aliases: List[str] = []

        match = candidate.get("match")
        if isinstance(match, dict):
            match_text = self._safe_string(match.get("text"))
            if match_text:
                aliases.append(match_text)

        aliases_data = entity_data.get("aliases", {})
        for lang in [self.language, "en"]:
            lang_aliases = aliases_data.get(lang, [])
            for item in lang_aliases:
                val = self._safe_string(item.get("value"))
                if val:
                    aliases.append(val)

        # deduplicado preservando orden
        seen = set()
        clean_aliases = []
        for a in aliases:
            key = self._normalize_text(a)
            if key and key not in seen:
                clean_aliases.append(a)
                seen.add(key)

        return clean_aliases

    def _extract_instance_of(self, entity_data: Dict[str, Any]) -> List[str]:
        """
        Extrae etiquetas si están disponibles; si no, devuelve IDs de claims P31.
        """
        results: List[str] = []
        claims = entity_data.get("claims", {}) or {}
        p31 = claims.get("P31", []) or []

        for claim in p31:
            try:
                mainsnak = claim.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                value = datavalue.get("value", {})
                qid = self._safe_string(value.get("id"))
                if qid:
                    results.append(qid)
            except Exception:
                continue

        return results

    # -------------------------------------------------------------------------
    # Helpers de texto
    # -------------------------------------------------------------------------

    def _safe_string(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _strip_accents(self, text: str) -> str:
        text = self._safe_string(text)
        if not text:
            return ""
        return "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )

    def _normalize_text(self, text: Any) -> str:
        text = self._safe_string(text).lower()
        text = self._strip_accents(text)
        text = re.sub(r"[^\w\s\-]", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _token_overlap(self, text_a: str, text_b: str) -> float:
        a = set(self._normalize_text(text_a).split())
        b = set(self._normalize_text(text_b).split())

        if not a or not b:
            return 0.0

        inter = a.intersection(b)
        union = a.union(b)

        if not union:
            return 0.0

        return len(inter) / len(union)
    
    


