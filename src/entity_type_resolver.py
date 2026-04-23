from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


class EntityTypeResolver:
    """
    Conservative tourism type resolver.

    The resolver gives priority to the entity mention, then uses local
    properties, ontology candidates and context only as supporting signals.
    It avoids returning generic final classes such as Place or Entity.
    """

    def __init__(self):
        self.weak_types = {
            "",
            "thing",
            "unknown",
            "entity",
            "item",
            "location",
            "person",
        }
        self.generic_final_types = {
            "Thing",
            "Entity",
            "Item",
            "Location",
            "Place",
            "TourismEntity",
            "TourismResource",
            "TourismService",
            "TourismOrRelatedFacility",
            "TourismOrganisation",
            "Organization",
            "Service",
            "Concept",
            "ConceptScheme",
            "Accommodation",
        }
        self.forbidden_final_types = {"Thing", "Entity", "Item", "Location"}

        self.type_aliases = {
            "activity": "DestinationExperience",
            "airport": "Airport",
            "bar": "Bar",
            "basilica": "Basilica",
            "bus station": "BusStation",
            "busstation": "BusStation",
            "cafe": "FoodEstablishment",
            "cathedral": "Cathedral",
            "chapel": "Chapel",
            "church": "Church",
            "concept": "ConceptScheme",
            "event": "Event",
            "excursion": "DestinationExperience",
            "festival": "Event",
            "guided tour": "Tour",
            "guidedtour": "Tour",
            "healthcarefacility": "PublicService",
            "healthcareorganization": "PublicService",
            "hotel": "Hotel",
            "museum": "Museum",
            "organisation": "TourismOrganisation",
            "organization": "TourismOrganisation",
            "park": "NaturalPark",
            "restaurant": "Restaurant",
            "route": "Route",
            "ruta": "Route",
            "stadium": "Stadium",
            "theatre": "Theater",
            "tourist attraction": "TouristAttractionSite",
            "touristattraction": "TouristAttractionSite",
            "touristattractionsite": "TouristAttractionSite",
            "train station": "TrainStation",
            "trainstation": "TrainStation",
        }

        self.min_semantic_confidence = 0.74
        self.strong_semantic_confidence = 0.86
        self.context_vote_threshold = 2.0

        # Ordered by specificity. Patterns run over normalized, accent-free text.
        raw_lexical_rules: List[Tuple[str, str, float]] = [
            (r"\b(oficina de turismo|punto de informacion turistica)\b", "TouristInformationOffice", 6.0),
            (r"\b(estacion de tren|estacion ferroviaria|apeadero)\b", "TrainStation", 6.0),
            (r"\b(estacion de autobuses|terminal de autobuses)\b", "BusStation", 6.0),
            (r"\b(aeropuerto)\b", "Airport", 6.0),
            (r"\b(ayuntamiento|casa consistorial)\b", "TownHall", 6.0),
            (r"\b(catedral)\b", "Cathedral", 6.0),
            (r"\b(basilica)\b", "Basilica", 6.0),
            (r"\b(iglesia|parroquia)\b", "Church", 5.8),
            (r"\b(capilla|ermita)\b", "Chapel", 5.8),
            (r"\b(monasterio)\b", "Monastery", 5.8),
            (r"\b(convento)\b", "Convent", 5.8),
            (r"\b(museo|pinacoteca)\b", "Museum", 5.8),
            (r"\b(alcazar)\b", "Alcazar", 5.8),
            (r"\b(castillo|fortaleza)\b", "Castle", 5.8),
            (r"\b(palacio)\b", "Palace", 5.7),
            (r"\b(torre|campanario|mirador torre)\b", "Tower", 5.4),
            (r"\b(muralla|murallas)\b", "Wall", 5.4),
            (r"\b(puente)\b", "Bridge", 5.4),
            (r"\b(plaza)\b", "Square", 5.2),
            (r"\b(jardin|jardines)\b", "Garden", 5.0),
            (r"\b(parque natural)\b", "NaturalPark", 5.4),
            (r"\b(parque de atracciones|parque tematico|isla magica)\b", "AmusementPark", 5.4),
            (r"\b(parque)\b", "Garden", 4.2),
            (r"\b(monumento|estatua|escultura|busto|conjunto escultorico)\b", "Monument", 5.1),
            (r"\b(yacimiento|sitio arqueologico|restos arqueologicos|antiquarium)\b", "ArcheologicalSite", 5.2),
            (r"\b(archivo de indias|archivo historico)\b", "HistoricalOrCulturalResource", 5.0),
            (r"\b(teatro)\b", "Theater", 5.1),
            (r"\b(auditorio|auditorium)\b", "Auditorium", 5.1),
            (r"\b(plaza de toros|real maestranza)\b", "BullRing", 5.2),
            (r"\b(estadio|campo de futbol)\b", "Stadium", 5.2),
            (r"\b(acuario)\b", "Aquarium", 5.2),
            (r"\b(biblioteca)\b", "Library", 5.0),
            (r"\b(mercado de abastos|mercado tradicional)\b", "TraditionalMarket", 5.2),
            (r"\b(mercado|mercadillo|zoco)\b", "TraditionalMarket", 4.6),
            (r"\b(hotel|hostal|parador|albergue)\b", "Hotel", 5.0),
            (r"\b(restaurante)\b", "Restaurant", 5.0),
            (r"\b(bar|taberna|cerveceria|bodega)\b", "Bar", 4.8),
            (r"\b(cafeteria|cafe)\b", "FoodEstablishment", 4.8),
            (r"\b(pump track|skatepark|skate)\b", "SportsCenter", 4.8),
            (r"\b(casco antiguo|barrio|casco historico)\b", "Neighborhood", 4.6),
            (r"\b(festival|bienal|concierto|exposicion|evento|feria|semana santa|procesion|via crucis|ciclo)\b", "Event", 5.2),
            (r"\b(ruta|camino|sendero|itinerario|recorrido|via verde)\b", "Route", 5.0),
            (r"\b(visita guiada|tour guiado|excursion)\b", "Tour", 4.8),
        ]
        self.lexical_rules = [
            (re.compile(pattern), label, weight)
            for pattern, label, weight in raw_lexical_rules
        ]

        self.family_compatibility = {
            "accommodation": {"Hotel", "AccommodationEstablishment"},
            "event": {"Event"},
            "experience": {"DestinationExperience", "Tour"},
            "food": {"Bar", "FoodEstablishment", "Restaurant", "TraditionalMarket", "WineBar"},
            "place": {
                "Airport",
                "Alcazar",
                "AmusementPark",
                "Aquarium",
                "ArcheologicalSite",
                "Auditorium",
                "Basilica",
                "Bridge",
                "BullRing",
                "BusStation",
                "Castle",
                "Cathedral",
                "Chapel",
                "Church",
                "Convent",
                "EventAttendanceFacility",
                "Garden",
                "HistoricalOrCulturalResource",
                "Library",
                "Monastery",
                "Monument",
                "Museum",
                "NaturalPark",
                "Palace",
                "Square",
                "Stadium",
                "Theater",
                "TouristAttractionSite",
                "TouristInformationOffice",
                "Tower",
                "TownHall",
                "TraditionalMarket",
                "TrainStation",
                "Wall",
            },
            "route": {"Itinerary", "Route", "Trail", "Tour"},
            "service": {"PublicService", "TourGuide", "TourismIntermediary"},
            "unknown": set(),
        }

    # ---------------------------------------------------------
    # Normalization helpers
    # ---------------------------------------------------------

    def _normalize_text(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _local_name(self, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        return raw.rstrip("/").split("#")[-1].split("/")[-1].strip()

    def _normalize_type(self, value: Any) -> str:
        raw = self._local_name(value)
        if not raw:
            return ""

        key = self._normalize_text(raw)
        compact = key.replace(" ", "")
        return self.type_aliases.get(key) or self.type_aliases.get(compact) or raw

    def _as_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _is_weak_type(self, value: Any) -> bool:
        return self._normalize_type(value).lower() in self.weak_types

    def _is_generic_final_type(self, value: Any) -> bool:
        return self._normalize_type(value) in self.generic_final_types

    def _is_forbidden_type(self, value: Any) -> bool:
        normalized = self._normalize_type(value)
        return normalized in self.forbidden_final_types or normalized.lower() in self.weak_types

    def _html_context_text(self, signals: Any) -> str:
        if not isinstance(signals, dict):
            return ""
        parts = [
            signals.get("tag") or "",
            signals.get("href") or "",
            signals.get("class") or "",
            signals.get("id") or "",
            signals.get("heading") or "",
            signals.get("parent_tag") or "",
            signals.get("parent_class") or "",
            signals.get("parent_id") or "",
            signals.get("link_text") or "",
            signals.get("link_href") or "",
        ]
        return self._normalize_text(" ".join(str(part) for part in parts if str(part).strip()))

    def _vote(
        self,
        votes: Dict[str, float],
        evidence: List[str],
        label: str,
        weight: float,
        source: str,
        family: str = "unknown",
    ) -> None:
        label = self._normalize_type(label)
        if not label or self._is_forbidden_type(label):
            return

        if self._is_generic_final_type(label):
            weight *= 0.35

        compatible = self.family_compatibility.get(family) or set()
        if compatible and label not in compatible:
            weight *= 0.45

        if weight <= 0:
            return

        votes[label] += weight
        evidence.append(f"{source}:{label}:{round(weight, 2)}")

    # ---------------------------------------------------------
    # Signal extraction
    # ---------------------------------------------------------

    def _detect_family(self, mention: str, context: str = "") -> str:
        text = self._normalize_text(f"{mention} {context[:500]}")
        mention_text = self._normalize_text(mention)

        if re.search(r"\b(festival|evento|concierto|bienal|feria|semana santa|procesion|via crucis|exposicion)\b", mention_text):
            return "event"

        if re.search(r"\b(camino|ruta|sendero|itinerario|recorrido|via verde)\b", mention_text):
            return "route"

        if re.search(r"\b(visita guiada|tour guiado|excursion)\b", mention_text):
            return "experience"

        if re.search(r"\b(restaurante|bar|cafeteria|cafe|taberna|bodega|cerveceria)\b", mention_text):
            return "food"

        if re.search(r"\b(hotel|hostal|parador|albergue)\b", mention_text):
            return "accommodation"

        if re.search(
            r"\b(ayuntamiento|catedral|museo|castillo|plaza|parque|jardin|iglesia|capilla|"
            r"basilica|palacio|alcazar|torre|puente|monasterio|convento|mercado|estadio|teatro)\b",
            mention_text,
        ):
            return "place"

        if re.search(r"\b(fecha|horario|entradas|programacion|concierto|festival)\b", text):
            return "event"

        return "unknown"

    def _lexical_candidates(self, text: str) -> List[Tuple[str, float]]:
        normalized = self._normalize_text(text)
        out: List[Tuple[str, float]] = []

        for pattern, label, weight in self.lexical_rules:
            if pattern.search(normalized):
                out.append((label, weight))

        return out

    def _iter_property_type_candidates(self, properties: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
        fields = (
            "class",
            "type",
            "primaryClass",
            "semantic_type",
            "classUri",
            "types",
            "typesRaw",
            "types_raw",
        )

        for key in fields:
            for value in self._as_list(properties.get(key)):
                label = self._normalize_type(value)
                if label:
                    yield key, label

        nested = properties.get("properties")
        if isinstance(nested, dict):
            for key in ("class", "type", "semantic_type"):
                label = self._normalize_type(nested.get(key))
                if label:
                    yield f"properties.{key}", label

    def _iter_html_context_candidates(
        self,
        mention: str,
        html_context_signals: Any,
        page_signals: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, str]]:
        mention_norm = self._normalize_text(mention)
        html_text = self._html_context_text(html_context_signals)
        page_text = self._normalize_text(
            " ".join([
                str((page_signals or {}).get("title") or ""),
                str((page_signals or {}).get("h1") or ""),
                str((page_signals or {}).get("breadcrumb") or ""),
                str((page_signals or {}).get("slug") or ""),
                str((page_signals or {}).get("url") or ""),
            ])
        )
        merged = f"{html_text} || {page_text}"
        candidates: List[Tuple[str, float, str]] = []

        def add(label: str, weight: float, reason: str) -> None:
            candidates.append((label, weight, reason))

        if any(term in merged for term in {"hotel", "hoteles", "hostal", "hostales", "alojamiento", "alojarse"}):
            if mention_norm.startswith(("hotel ", "hostal ", "albergue ", "parador ")):
                add("Hotel", 3.4, "html_accommodation_strong")
            elif any(term in mention_norm for term in {"hotel", "hostal", "albergue", "parador"}):
                add("Hotel", 2.4, "html_accommodation")

        if any(term in merged for term in {"restaurante", "restaurantes", "gastronomia", "donde comer"}):
            if mention_norm.startswith("restaurante "):
                add("Restaurant", 3.1, "html_food_strong")
            elif "restaurante" in mention_norm:
                add("Restaurant", 2.2, "html_food")

        if any(term in merged for term in {"bar", "bares", "taberna", "cafeteria", "cafeterias"}):
            if mention_norm.startswith(("bar ", "taberna ", "cafeteria ", "cafe ")):
                add("Bar", 3.0, "html_bar_strong")
            elif any(term in mention_norm for term in {"bar", "taberna", "cafeteria", "cafe"}):
                add("Bar", 2.0, "html_bar")

        if any(term in merged for term in {"visitas guiadas", "tour", "tours", "guias turistico culturales"}):
            if any(term in mention_norm for term in {"tour", "visita", "guiada"}):
                add("Tour", 2.0, "html_tour")

        if any(term in merged for term in {"museo", "museos"}):
            if "museo" in mention_norm:
                add("Museum", 2.0, "html_museum")

        if any(term in merged for term in {"mercado", "mercados"}):
            if "mercado" in mention_norm:
                add("TraditionalMarket", 2.0, "html_market")

        return candidates

    def _clean_mention_for_resolution(
        self,
        mention: str,
        context: str = "",
        page_signals: Optional[Dict[str, Any]] = None,
    ) -> str:
        mention_norm = self._normalize_text(mention)
        context_norm = self._normalize_text(context)
        page_norm = self._normalize_text(
            " ".join([
                str((page_signals or {}).get("title") or ""),
                str((page_signals or {}).get("h1") or ""),
                str((page_signals or {}).get("breadcrumb") or ""),
                str((page_signals or {}).get("slug") or ""),
                str((page_signals or {}).get("url") or ""),
            ])
        )

        prefix = "ayuntamiento de pamplona "
        if mention_norm.startswith(prefix):
            strong_municipal_terms = {
                "casa consistorial", "plaza consistorial", "tramite", "municipal", "concejal", "alcaldia", "alcalde",
            }
            false_footer_tails = {
                "casco antiguo",
                "pump track",
                "frente ciudadela",
                "san fermin",
                "estrellas michelin",
                "queso",
                "alojamientos",
                "verde",
                "reserva",
                "preguntas",
                "mercados",
                "agroturismos",
                "cordero",
                "menestra",
                "patxaran",
                "actas",
                "pimientos",
                "ajoarriero",
                "trucha",
                "pochas",
                "esparragos",
                "cuajada",
                "chistorra",
                "goxua",
                "pantxineta",
                "fritos",
                "planes",
                "cultura",
                "hostelet",
                "informacion general",
            }
            merged = f"{context_norm} || {page_norm}"
            if any(term in mention_norm for term in false_footer_tails):
                remainder = mention[len(prefix):].strip()
                if remainder:
                    return remainder
            if not any(term in merged for term in strong_municipal_terms):
                remainder = mention[len(prefix):].strip()
                if remainder:
                    return remainder

        return mention

    def _iter_description_candidates(
        self,
        properties: Dict[str, Any],
        page_signals: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float, str]]:
        text = self._normalize_text(
            " ".join([
                str(properties.get("short_description") or properties.get("shortDescription") or ""),
                str(properties.get("long_description") or properties.get("longDescription") or ""),
                str(properties.get("description") or ""),
                str((page_signals or {}).get("title") or ""),
                str((page_signals or {}).get("h1") or ""),
            ])
        )
        candidates: List[Tuple[str, float, str]] = []

        def add(label: str, weight: float, reason: str) -> None:
            candidates.append((label, weight, reason))

        if re.search(r"\b(hotel|hostal|alojamiento|habitaciones|estrellas|recepcion|recepción)\b", text):
            add("Hotel", 2.8, "description_accommodation")
        if re.search(r"\b(restaurante|cocina|gastronomia|gastronomica|menu degustacion|menú degustación)\b", text):
            add("Restaurant", 2.4, "description_food")
        if re.search(r"\b(bar|pintxos|pinchos|taberna|cerveceria|cervecería)\b", text):
            add("Bar", 2.2, "description_bar")
        if re.search(r"\b(museo|coleccion|colección|exposicion|exposición)\b", text):
            add("Museum", 2.4, "description_museum")
        if re.search(r"\b(muralla|baluarte|fortificacion|fortificación|sistema defensivo)\b", text):
            add("Wall", 2.3, "description_wall")
        if re.search(r"\b(festival|programacion cultural|programación cultural|conciertos|actuaciones|teatro|circo)\b", text):
            add("Event", 2.3, "description_event")
        if re.search(r"\b(mercado|producto local|puestos|artesano)\b", text):
            add("TraditionalMarket", 2.1, "description_market")
        if re.search(r"\b(queso|postre|licor|embutido|plato|gastronomico|gastronómico)\b", text):
            add("FoodEstablishment", 1.6, "description_food_product")

        if re.search(r"\b(hostal|hostelet|pamplona beds|room pamplona|apartamento|apartamentos)\b", text):
            add("Hotel", 2.4, "description_lodging")

        if re.search(r"\b(hostel|albergue|albergues|pensiones y hostales)\b", text):
            add("Hostel", 2.7, "description_hostel")
        if re.search(r"\b(teatro|coliseo|escenario|espectaculos)\b", text):
            add("Theater", 2.4, "description_theater")
        if re.search(r"\b(pump track|skate park|skatepark|skateboarding|rocodromo|rocopolis|deporte sobre ruedas)\b", text):
            add("SportsCenter", 2.5, "description_sport")
        if re.search(r"\b(casco antiguo|barrio historico|centro historico)\b", text):
            add("Neighborhood", 2.4, "description_neighborhood")
        if re.search(r"\b(ruta cicloturista|cicloturismo|senderismo|peregrinos|via verde)\b", text):
            add("Route", 2.4, "description_route")

        return candidates

    def _iter_image_context_candidates(self, properties: Dict[str, Any]) -> List[Tuple[str, float, str]]:
        image_text = self._normalize_text(
            " ".join([
                str(properties.get("image") or ""),
                str(properties.get("mainImage") or ""),
            ])
        )
        candidates: List[Tuple[str, float, str]] = []

        def add(label: str, weight: float, reason: str) -> None:
            candidates.append((label, weight, reason))

        if any(term in image_text for term in {"hotel", "hostal", "hostelet", "alojamiento"}):
            add("Hotel", 1.6, "image_accommodation")
        if any(term in image_text for term in {"pump_track", "pump-track", "skate", "rocopolis"}):
            add("SportsCenter", 1.5, "image_sport")
        if any(term in image_text for term in {"queso", "patxaran", "piquillo", "cuajada", "goxua", "pantxineta", "chistorra", "fritos"}):
            add("FoodEstablishment", 1.2, "image_food_product")

        return candidates

    def _candidate_label(self, cand: Dict[str, Any]) -> str:
        for key in ("class", "type", "label", "name", "id", "uri"):
            label = self._normalize_type(cand.get(key))
            if label:
                return label
        return ""

    def _candidate_score(self, cand: Dict[str, Any]) -> float:
        for key in ("score", "confidence", "similarity"):
            try:
                if cand.get(key) is not None:
                    return float(cand.get(key) or 0)
            except (TypeError, ValueError):
                continue
        return 0.0

    # ---------------------------------------------------------
    # Final decision
    # ---------------------------------------------------------

    def _best(self, votes: Dict[str, float]) -> Dict[str, Any]:
        if not votes:
            return {"class": "Unknown", "score": 0.0, "margin": 0.0}

        ordered = sorted(votes.items(), key=lambda x: (-x[1], self._is_generic_final_type(x[0]), x[0]))
        best_label, best_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0.0
        margin = best_score - second_score

        min_score = 3.2 if not self._is_generic_final_type(best_label) else 7.0
        min_margin = 0.65 if best_score >= 5.0 else 1.0

        if best_score < min_score or margin < min_margin:
            return {"class": "Unknown", "score": best_score, "margin": margin}

        if self._is_generic_final_type(best_label):
            return {"class": "Unknown", "score": best_score, "margin": margin}

        return {"class": best_label, "score": best_score, "margin": margin}

    def _result(
        self,
        final_class: str,
        family: str,
        score: float,
        margin: float,
        evidence: List[str],
        semantic_type: str = "",
        semantic_score: float = 0.0,
        ontology_candidates_seen: int = 0,
    ) -> Dict[str, Any]:
        final_class = self._normalize_type(final_class) or "Unknown"
        if self._is_generic_final_type(final_class) or self._is_forbidden_type(final_class):
            final_class = "Unknown"

        return {
            "class": final_class,
            "type": final_class,
            "family": family,
            "score": round(float(score or 0.0), 4),
            "margin": round(float(margin or 0.0), 4),
            "evidence": evidence,
            "semantic_type": semantic_type,
            "semantic_score": round(float(semantic_score or 0.0), 4),
            "ontology_candidates_seen": ontology_candidates_seen,
        }

    def resolve(
        self,
        mention: str,
        context: str = "",
        block_text: str = "",
        page_signals: Optional[Dict[str, Any]] = None,
        properties: Optional[Dict[str, Any]] = None,
        expected_type: Optional[str] = None,
        ontology_candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        properties = properties or {}
        page_signals = page_signals or {}
        ontology_candidates = ontology_candidates or []

        mention = str(mention or "").strip()
        context = str(context or "")
        block_text = str(block_text or "")
        mention = self._clean_mention_for_resolution(
            mention=mention,
            context=" ".join([context[:1200], block_text[:600]]),
            page_signals=page_signals,
        )

        family = self._detect_family(mention, context or block_text)
        mention_norm = self._normalize_text(mention)
        html_context_signals = properties.get("html_context_signals") if isinstance(properties, dict) else {}

        hard_reject_patterns = [
            r"^visitas guiadas$",
            r"^actividades$",
            r"^culturales visitas$",
            r"^produccion agraria ecologica$",
            r"^sostenibilidad turistica$",
            r"^interes turistico internacional$",
            r"^postres queso roncal$",
            r"^actividades .* skate$",
            r"^actividades .* pump track$",
            r"^informacion general$",
            r"^reserva$",
            r"^preguntas$",
            r"^planes$",
            r"^cultura$",
            r"^verde$",
            r"^mercados$",
            r"^actas$",
            r"^queso roncal$",
            r"^queso idiazabal$",
            r"^patxaran$",
            r"^ajoarriero$",
            r"^trucha( a la navarra)?$",
            r"^pochas$",
            r"^esparragos$",
            r"^cuajada$",
            r"^chistorra$",
            r"^goxua$",
            r"^pantxineta$",
            r"^fritos$",
            r"^hoteles$",
            r"^restaurantes$",
            r"^albergues$",
            r"^campings$",
            r"^pensiones$",
            r"^pensiones y hostales$",
            r"^paseos y rutas$",
            r"^excursiones$",
            r"^todos los lugares$",
            r"^todas las noticias$",
            r"^categorias$",
            r"^categorías$",
        ]
        for pattern in hard_reject_patterns:
            if re.search(pattern, mention_norm):
                return self._result(
                    final_class="Unknown",
                    family="unknown",
                    score=0.0,
                    margin=0.0,
                    evidence=["hard_reject:non_entity"],
                    ontology_candidates_seen=len(ontology_candidates),
                )

        # High-precision overrides for common tourism cases.
        hard_rules = [
            (r"\bplaza de toros\b", "BullRing", "place"),
            (r"\b(estacion de autobuses|estacion de bus|terminal de autobuses)\b", "BusStation", "place"),
            (r"\b(plaza de armas|prado de san sebastian)\b", "BusStation", "place"),
            (r"\b(estacion de santa justa|estacion de tren|estacion ferroviaria)\b", "TrainStation", "place"),
            (r"\b(ayuntamiento|casa consistorial)\b", "TownHall", "place"),
            (r"\bcamino de santiago\b", "Route", "route"),
            (r"\bsan fermin(es)?\b", "Event", "event"),
            (r"\bsemana santa\b", "Event", "event"),
            (r"^plaza\b", "Square", "place"),
            (r"^museo\b", "Museum", "place"),
            (r"^castillo\b", "Castle", "place"),
            (r"^palacio\b", "Palace", "place"),
            (r"^parque\b", "Garden", "place"),
        ]
        for pattern, label, hard_family in hard_rules:
            if re.search(pattern, mention_norm):
                if label == "TownHall" and not re.search(r"^(ayuntamiento|casa consistorial)\b", mention_norm):
                    continue
                return self._result(
                    final_class=label,
                    family=hard_family,
                    score=10.0,
                    margin=10.0,
                    evidence=[f"hard_rule:{label}"],
                    ontology_candidates_seen=len(ontology_candidates),
                )

        votes: Dict[str, float] = defaultdict(float)
        evidence: List[str] = []

        # Mention evidence is strongest because context often describes tours
        # around an entity rather than the entity itself.
        for label, weight in self._lexical_candidates(mention):
            self._vote(votes, evidence, label, weight, "mention", family)
        if mention_norm.startswith(("hotel ", "gran hotel ", "hostal ", "alojamientos ", "apartamentos ")):
            self._vote(votes, evidence, "Hotel", 3.2, "mention_lodging_prefix", family)
        if mention_norm.startswith(("restaurante ", "asador ")):
            self._vote(votes, evidence, "Restaurant", 3.0, "mention_food_prefix", family)

        normalized_expected = self._normalize_type(expected_type)
        if normalized_expected:
            self._vote(votes, evidence, normalized_expected, 1.1, "expected_type", family)

        for label, weight, reason in self._iter_html_context_candidates(
            mention=mention,
            html_context_signals=html_context_signals,
            page_signals=page_signals,
        ):
            self._vote(votes, evidence, label, weight, reason, family)

        for label, weight, reason in self._iter_description_candidates(
            properties=properties,
            page_signals=page_signals,
        ):
            self._vote(votes, evidence, label, weight, reason, family)

        for label, weight, reason in self._iter_image_context_candidates(properties):
            self._vote(votes, evidence, label, weight, reason, family)

        for source, label in self._iter_property_type_candidates(properties):
            weight = 2.0 if source in {"class", "type", "primaryClass"} else 1.2
            self._vote(votes, evidence, label, weight, source, family)

        semantic_type = ""
        semantic_score = 0.0
        for cand in ontology_candidates[:5]:
            label = self._candidate_label(cand)
            score = self._candidate_score(cand)
            if not label:
                continue
            if score > semantic_score:
                semantic_type = label
                semantic_score = score
            if score >= self.strong_semantic_confidence:
                self._vote(votes, evidence, label, 2.4, "ontology_strong", family)
            elif score >= self.min_semantic_confidence:
                self._vote(votes, evidence, label, 1.1, "ontology_weak", family)

        # Context has lower weight and only participates when the mention did
        # not already provide a decisive specific type.
        mention_vote = max(votes.values(), default=0.0)
        if mention_vote < 5.0:
            context_text = " ".join([block_text[:1200], context[:1800]])
            context_hits = self._lexical_candidates(context_text)
            for label, weight in context_hits[:4]:
                self._vote(
                    votes,
                    evidence,
                    label,
                    min(self.context_vote_threshold, weight * 0.35),
                    "context",
                    family,
                )

        page_expected = self._normalize_type(page_signals.get("expected_type") or page_signals.get("type"))
        if page_expected:
            self._vote(votes, evidence, page_expected, 0.7, "page_signal", family)

        best = self._best(votes)

        return self._result(
            final_class=best["class"],
            family=family,
            score=best["score"],
            margin=best["margin"],
            evidence=evidence,
            semantic_type=semantic_type,
            semantic_score=semantic_score,
            ontology_candidates_seen=len(ontology_candidates),
        )
