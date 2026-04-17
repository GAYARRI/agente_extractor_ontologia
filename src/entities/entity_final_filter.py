from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple


class EntityFinalFilter:
    """
    Final conservative filter for already-ranked entities.

    Goal:
    - remove obvious garbage mentions
    - remove UI/menu/category fragments
    - remove malformed phrase chunks
    - apply lightweight page-topic compatibility checks
    """

    def __init__(self) -> None:
        self.stop_phrases = {
            "facebook",
            "instagram",
            "youtube",
            "twitter",
            "x",
            "linkedin",
            "tiktok",
            "ver mas",
            "ver más",
            "leer mas",
            "leer más",
            "mas informacion",
            "más información",
            "ultima",
            "última",
            "ultimas",
            "últimas",
            "buscar",
            "busca",
            "newsletter",
            "cookies",
            "politica",
            "política",
            "privacidad",
            "aviso legal",
            "contacto",
            "menu",
            "menú",
        }

        self.bad_exact_names = {
            "facebook instagram",
            "monumentos mercados ultimas",
            "monumentos mercados últimas",
            "pamplona viajar",
            "navarra barrio",
            "desde puente",
            "origen siglos",
            "club dejate",
            "club déjate",
            "reyno gourmet busca",
            "postres queso roncal",
            "interes turistico internacional",
            "interés turístico internacional",
            "indicaciones geograficas protegidas",
            "indicaciones geográficas protegidas",
            "navarra la ruta",
            "verano cultural",
        }

        self.bad_contains = {
            "facebook",
            "instagram",
            "ultima",
            "última",
            "ultimas",
            "últimas",
            "busca",
            "haz clic",
            "suscrib",
            "newsletter",
            "privacidad",
            "cookies",
        }

        self.leading_bad_words = {
            "desde",
            "con",
            "para",
            "durante",
            "entre",
            "sobre",
            "hacia",
            "segun",
            "según",
            "frecuentaba",
            "indicaciones",
            "origen",
        }

        self.generic_category_words = {
            "monumentos",
            "mercados",
            "ultimas",
            "últimas",
            "categoria",
            "categorías",
            "categorias",
            "planes",
            "blog",
            "agenda",
            "noticias",
            "profesional",
            "viajar",
            "ruta",
            "rutas",
            "historia",
            "cultura",
            "gastronomia",
            "gastronomía",
            "postres",
            "queso",
            "mercado",
            "mercados",
            "barrios",
            "barrio",
            "ultimas",
            "últimas",
        }

        self.allowed_unknown_names = {
            "cafe iruna",
            "café iruña",
            "caf\u00e9 iru\u00f1a",
            "navarra arena",
            "fronton jito alai",
            "frontón jito alai",
            "festival santas pascuas",
            "flamenco on fire",
            "parque de la media luna",
            "catedral de pamplona",
            "ayuntamiento de pamplona plaza consistorial",
        }

        self.class_aliases = {
            "townhall": "TownHall",
            "square": "Square",
            "cathedral": "Cathedral",
            "basilica": "Basilica",
            "church": "Church",
            "chapel": "Chapel",
            "monastery": "Monastery",
            "museum": "Museum",
            "castle": "Castle",
            "alcazar": "Alcazar",
            "monument": "Monument",
            "event": "Event",
            "foodestablishment": "FoodEstablishment",
            "unknown": "Unknown",
            "sportsvenue": "SportsVenue",
            "arena": "Arena",
            "theatre": "Theatre",
            "park": "Park",
            "garden": "Garden",
            "bridge": "Bridge",
            "market": "Market",
            "guidedtour": "GuidedTour",
            "excursion": "Excursion",
            "activity": "Activity",
        }

    # -------------------------------------------------------------------------
    # Text helpers
    # -------------------------------------------------------------------------

    def _strip_accents(self, text: str) -> str:
        return "".join(
            ch for ch in unicodedata.normalize("NFD", text)
            if unicodedata.category(ch) != "Mn"
        )

    def _norm(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        text = self._strip_accents(text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _norm_type(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        short = text.split("#")[-1].split("/")[-1].strip()
        return short

    def _get_name(self, entity: Dict[str, Any]) -> str:
        return str(
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        ).strip()

    def _get_primary_class(self, entity: Dict[str, Any]) -> str:
        types = entity.get("types")
        if isinstance(types, list) and types:
            for t in types:
                norm_t = self._norm_type(t)
                if norm_t and norm_t.lower() not in {"location", "thing", "entity", "item"}:
                    return norm_t

        entity_class = self._norm_type(entity.get("class"))
        if entity_class:
            return entity_class

        entity_type = self._norm_type(entity.get("type"))
        if entity_type:
            return entity_type

        return "Unknown"

    def _page_topic(self, url: str, entity: Dict[str, Any]) -> str:
        u = self._norm(url)
        text = self._norm(
            " ".join([
                str(entity.get("shortDescription") or ""),
                str(entity.get("longDescription") or ""),
                str(entity.get("description") or ""),
            ])
        )

        source = f"{u} {text}"

        if any(k in source for k in [
            "gastronomia", "gastronomia", "gastronomy", "pintxo", "comer", "food"
        ]):
            return "gastronomy"

        if any(k in source for k in [
            "camino-de-santiago", "camino de santiago", "pilgrim", "peregrin"
        ]):
            return "camino"

        if any(k in source for k in [
            "pelota-vasca", "pelota vasca", "fronton", "frontón", "arena"
        ]):
            return "sports"

        if any(k in source for k in [
            "san-fermin", "san fermin", "festival", "fiesta", "evento"
        ]):
            return "event"

        if any(k in source for k in [
            "historia", "history", "patrimonio", "murallas", "catedral"
        ]):
            return "history"

        if any(k in source for k in [
            "cultura", "culture", "museo", "museum", "teatro"
        ]):
            return "culture"

        return "generic"

    # -------------------------------------------------------------------------
    # Quality checks
    # -------------------------------------------------------------------------

    def _looks_like_ui_noise(self, name: str) -> bool:
        n = self._norm(name)

        if not n:
            return True

        if n in self.bad_exact_names:
            return True

        if n in self.stop_phrases:
            return True

        if any(bad in n for bad in self.bad_contains):
            return True

        return False

    def _looks_like_bad_phrase_fragment(self, name: str) -> bool:
        n = self._norm(name)
        tokens = n.split()

        if not tokens:
            return True

        if tokens[0] in self.leading_bad_words:
            return True

        if len(tokens) >= 3:
            generic_hits = sum(1 for t in tokens if t in self.generic_category_words)
            if generic_hits >= 2:
                return True

        # Very weak chunks like "origen siglos", "desde puente"
        if len(tokens) == 2 and tokens[0] in self.leading_bad_words:
            return True

        # obvious menu/list chunks
        if len(tokens) >= 3 and all(t in self.generic_category_words for t in tokens[:3]):
            return True

        return False

    def _looks_too_generic_for_final(self, name: str, primary_class: str) -> bool:
        n = self._norm(name)

        if n in self.allowed_unknown_names:
            return False

        tokens = n.split()

        # one-word generic names
        if len(tokens) == 1 and primary_class == "Unknown":
            return True

        # very generic two-word unknowns
        if len(tokens) == 2 and primary_class == "Unknown":
            if tokens[0] in {"navarra", "pamplona", "origen", "desde", "club", "verano"}:
                return True

        return False

    def _class_page_mismatch(self, primary_class: str, name: str, url: str, entity: Dict[str, Any]) -> bool:
        topic = self._page_topic(url, entity)
        n = self._norm(name)
        c = self.class_aliases.get(primary_class.lower(), primary_class)

        # lexical rescue
        if "arena" in n and c in {"Arena", "SportsVenue"}:
            return False
        if "fronton" in n or "frontón" in name.lower():
            if c in {"SportsVenue", "Arena", "Unknown"}:
                return False
        if "festival" in n and c == "Event":
            return False
        if "catedral" in n and c == "Cathedral":
            return False
        if "parque" in n and c in {"Park", "Garden", "Unknown"}:
            return False
        if "cafe" in n or "café" in name.lower():
            if c in {"FoodEstablishment", "Unknown"}:
                return False

        if topic == "sports":
            if c in {"Basilica", "Cathedral", "Chapel", "Monastery", "Castle"} and "castillo" not in n:
                return True

        if topic == "gastronomy":
            if c in {"Castle", "Basilica", "Cathedral", "Monument"}:
                return True

        if topic == "camino":
            if c in {"Basilica", "Castle"} and "castillo" not in n and "basilica" not in n and "basílica" not in n:
                return True

        if topic == "event":
            if c in {"Castle", "Basilica", "Cathedral", "Monument"} and "festival" in n:
                return True

        return False

    def _entity_has_minimum_signal(self, entity: Dict[str, Any]) -> bool:
        name = self._get_name(entity)
        if not name.strip():
            return False

        # image alone is not enough
        text_len = max(
            len(str(entity.get("shortDescription") or "")),
            len(str(entity.get("description") or "")),
            len(str(entity.get("longDescription") or "")),
        )

        if text_len < 20 and not entity.get("wikidataId"):
            return False

        return True

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def evaluate(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        name = self._get_name(entity)
        url = str(entity.get("url") or entity.get("sourceUrl") or "").strip()
        primary_class = self._get_primary_class(entity)

        reasons: List[str] = []

        if not self._entity_has_minimum_signal(entity):
            reasons.append("minimum_signal")

        if self._looks_like_ui_noise(name):
            reasons.append("ui_noise")

        if self._looks_like_bad_phrase_fragment(name):
            reasons.append("phrase_fragment")

        if self._looks_too_generic_for_final(name, primary_class):
            reasons.append("too_generic")

        if self._class_page_mismatch(primary_class, name, url, entity):
            reasons.append("class_page_mismatch")

        decision = "reject" if reasons else "keep"

        return {
            "decision": decision,
            "reasons": reasons,
            "name": name,
            "primary_class": primary_class,
            "url": url,
        }

    def filter(self, entities: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        kept: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            audit = self.evaluate(entity)
            item = dict(entity)
            item["final_filter_audit"] = audit

            if audit["decision"] == "keep":
                kept.append(item)
            else:
                rejected.append(item)

        return kept, rejected