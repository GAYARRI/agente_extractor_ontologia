from __future__ import annotations

import re
import time
import unicodedata
from typing import Any, Dict, List, Optional

import requests


class WikidataLinker:
    """
    Linker conservador contra Wikidata.

    Objetivos:
    - evitar consultas basura con fragmentos narrativos
    - soportar rate-limit (429)
    - devolver resultados consistentes aunque falle Wikidata
    - exponer get_entity_data() para otros componentes del pipeline
    """

    WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
    WIKIDATA_ENTITY_DATA_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

    def __init__(
        self,
        lang: str = "es",
        user_agent: str = "TourismOntologyAgent/1.0",
        timeout: int = 20,
        max_retries: int = 2,
        retry_sleep: float = 1.5,
        debug: bool = False,
    ):
        self.lang = lang
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_sleep = retry_sleep
        self.debug = debug

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            }
        )

        self.ui_terms = {
            "ir al contenido",
            "reserva tu actividad",
            "ver más",
            "ver mas",
            "leer más",
            "leer mas",
            "mostrar más",
            "mostrar mas",
            "todos los derechos reservados",
            "accesibilidad",
            "guías convention bureau",
            "guias convention bureau",
            "área profesional",
            "area profesional",
            "mapas",
            "contacto",
            "google maps",
            "copiar dirección",
            "copiar direccion",
        }

        self.leading_noise_patterns = [
            r"^(actividad)\b",
            r"^(agenda)\b",
            r"^(programa)\b",
            r"^(experiencias)\b",
            r"^(visita guiada)\b",
            r"^(ir al contenido)\b",
            r"^(reserva tu actividad)\b",
            r"^(por supuesto)\b",
            r"^(también|tambien|además|ademas)\b",
        ]

        self.trailing_noise_patterns = [
            r"\b(ver|más|mas|también|tambien|comenzaremos)$",
            r"\b(monumento|monumentos|espacios|museo|museos|lugar|lugares)$",
            r"\b(pago recomendado)$",
        ]

        self.phrase_markers = {
            "es",
            "son",
            "fue",
            "fueron",
            "ser",
            "puede",
            "pueden",
            "ofrece",
            "ofrecen",
            "comenzaremos",
            "comienza",
            "combina",
            "combinan",
            "disfruta",
            "disfrutar",
            "vivir",
            "tienen",
            "data",
            "ocurre",
            "permite",
            "permiten",
            "llegaremos",
            "visitaremos",
        }

        self.stop_tokens = {
            "de",
            "del",
            "la",
            "las",
            "el",
            "los",
            "y",
            "en",
            "con",
            "por",
            "para",
            "un",
            "una",
            "unos",
            "unas",
            "al",
        }

    # ------------------------------------------------------------------
    # Normalización
    # ------------------------------------------------------------------

    def _norm(self, text: Any) -> str:
        text = "" if text is None else str(text)
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _norm_low(self, text: Any) -> str:
        text = self._norm(text).lower()
        text = re.sub(r"[“”\"'`´]", "", text)
        return text

    def _strip_accents(self, text: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )

    def _tokens(self, text: str) -> List[str]:
        return [t for t in re.split(r"[^\wáéíóúñü]+", self._norm_low(text)) if t]

    # ------------------------------------------------------------------
    # Ruido / calidad de consulta
    # ------------------------------------------------------------------

    def _clean_name(self, text: str) -> str:
        value = self._norm(text)

        for pat in self.leading_noise_patterns:
            value = re.sub(pat, "", value, flags=re.IGNORECASE).strip()

        for pat in self.trailing_noise_patterns:
            value = re.sub(pat, "", value, flags=re.IGNORECASE).strip()

        value = re.sub(r"\s+", " ", value).strip(" -|,;:")
        return value

    def _looks_like_ui_fragment(self, text: str) -> bool:
        low = self._norm_low(text)
        if not low:
            return True
        return any(term in low for term in self.ui_terms)

    def _looks_like_phrase_fragment(self, text: str) -> bool:
        low = self._norm_low(text)
        tokens = self._tokens(low)

        if not tokens:
            return True

        if re.search(r"\b(quién|quien|cuándo|cuando|cómo|como)\b", low):
            return True

        if len(tokens) >= 6:
            return True

        if any(tok in self.phrase_markers for tok in tokens) and len(tokens) >= 4:
            return True

        return False

    def _looks_like_foreign_noise(self, text: str) -> bool:
        low = self._norm_low(text)

        foreign_patterns = [
            r"\btodos los lugares\b",
            r"\bmultitud de actividades\b",
            r"\bplanifica tu viaje\b",
            r"\bdescubre pamplona\b",
            r"\bmoverse por pamplona\b",
            r"\bqué ver\b",
            r"\bque ver\b",
            r"\bqué hacer\b",
            r"\bque hacer\b",
        ]
        return any(re.search(pat, low, flags=re.IGNORECASE) for pat in foreign_patterns)

    def _looks_like_person_name(self, text: str) -> bool:
        """
        Señal débil. No fuerza mapeo a person.
        Solo describe forma del nombre.
        """
        name = self._norm(text)
        if not name:
            return False

        parts = [p for p in re.split(r"\s+", name) if p]
        if len(parts) < 2 or len(parts) > 4:
            return False

        uppercase_like = 0
        for p in parts:
            if re.match(r"^[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü\-]+$", p):
                uppercase_like += 1

        return uppercase_like >= 2

    def _has_instance_signal(self, text: str) -> bool:
        low = self._norm_low(text)
        signals = [
            "ayuntamiento",
            "catedral",
            "iglesia",
            "basílica",
            "basilica",
            "capilla",
            "monasterio",
            "convento",
            "castillo",
            "alcázar",
            "alcazar",
            "palacio",
            "museo",
            "mercado",
            "plaza",
            "parque",
            "teatro",
            "puente",
            "festival",
            "feria",
            "congreso",
            "camino",
            "ruta",
            "sendero",
            "hotel",
            "hostal",
            "albergue",
            "camping",
            "centro de interpretación",
            "centro de acogida",
        ]
        return any(s in low for s in signals)

    def _is_queryable_name(self, text: str) -> bool:
        cleaned = self._clean_name(text)
        low = self._norm_low(cleaned)
        tokens = self._tokens(cleaned)

        if not cleaned:
            return False
        if self._looks_like_ui_fragment(cleaned):
            return False
        if self._looks_like_foreign_noise(cleaned):
            return False
        if self._looks_like_phrase_fragment(cleaned):
            return False
        if len(tokens) == 1 and not self._has_instance_signal(cleaned):
            return False

        return True

    # ------------------------------------------------------------------
    # Mapeo de clase -> tipo de búsqueda Wikidata
    # ------------------------------------------------------------------

    def _map_class_for_search(
        self,
        entity_class: Optional[str],
        entity_name: str = "",
        description: str = "",
    ) -> Optional[str]:
        """
        Mapea clases turísticas a una familia Wikidata aproximada.
        Muy conservador.
        """
        cls = self._norm_low(entity_class)
        name = self._norm_low(entity_name)
        desc = self._norm_low(description)

        if not cls or cls in {"unknown", "thing", "entity", "item", "location"}:
            # Solo señales MUY fuertes
            if "camino de santiago" in name:
                return "place"
            if any(k in name for k in ["festival", "feria", "congreso", "san fermín", "san fermin"]):
                return "event"
            if any(k in name for k in ["ayuntamiento", "catedral", "iglesia", "palacio", "castillo", "museo", "plaza", "parque"]):
                return "place"
            return "unknown"

        place_classes = {
            "townhall",
            "cathedral",
            "church",
            "chapel",
            "basilica",
            "castle",
            "alcazar",
            "palace",
            "museum",
            "square",
            "park",
            "garden",
            "route",
            "stadium",
            "monument",
        }

        event_classes = {
            "event",
            "festivity",
            "festival",
            "fair",
            "conference",
        }

        concept_classes = {
            "conceptscheme",
            "concept",
        }

        if cls in place_classes:
            return "place"
        if cls in event_classes:
            return "event"
        if cls in concept_classes:
            return "concept"

        # persona como categoría turística NO existe; no usar como default
        if self._looks_like_person_name(entity_name):
            if self._has_instance_signal(entity_name) or any(
                k in desc for k in ["estatua", "escultura", "monumento", "retrato", "busto"]
            ):
                return "place"

        return "unknown"

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _request_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        retries = 0

        while True:
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                )

                if response.status_code == 429:
                    if retries >= self.max_retries:
                        if self.debug:
                            print(f"⚠️ Wikidata 429 persistente en {url}")
                        return None

                    retries += 1
                    if self.debug:
                        print(f"⚠️ Wikidata 429. Reintentando en {self.retry_sleep}s...")
                    time.sleep(self.retry_sleep)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                if self.debug:
                    print(f"⚠️ request error for {url}: {e}")
                return None
            except ValueError as e:
                if self.debug:
                    print(f"⚠️ json decode error for {url}: {e}")
                return None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _search_candidates(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query = self._clean_name(query)
        if not self._is_queryable_name(query):
            return []

        payload = {
            "action": "wbsearchentities",
            "format": "json",
            "language": self.lang,
            "uselang": self.lang,
            "search": query,
            "limit": limit,
            "type": "item",
        }

        data = self._request_json(self.WIKIDATA_SEARCH_URL, params=payload)
        if not data or "search" not in data:
            return []

        return data.get("search", []) or []

    def _get_entity_data(self, qid: str) -> Optional[Dict[str, Any]]:
        if not qid:
            return None

        url = self.WIKIDATA_ENTITY_DATA_URL.format(qid=qid)
        return self._request_json(url)

    def get_entity_data(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Método público requerido por knowledge_graph_builder.py
        """
        return self._get_entity_data(qid)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _candidate_label(self, candidate: Dict[str, Any]) -> str:
        return self._norm(candidate.get("label") or candidate.get("display", {}).get("label", {}).get("value") or "")

    def _candidate_description(self, candidate: Dict[str, Any]) -> str:
        return self._norm(candidate.get("description") or candidate.get("display", {}).get("description", {}).get("value") or "")

    def _text_similarity(self, a: str, b: str) -> float:
        a_norm = self._strip_accents(self._norm_low(a))
        b_norm = self._strip_accents(self._norm_low(b))

        if not a_norm or not b_norm:
            return 0.0
        if a_norm == b_norm:
            return 1.0
        if a_norm in b_norm or b_norm in a_norm:
            return 0.85

        a_tokens = {t for t in self._tokens(a_norm) if t not in self.stop_tokens}
        b_tokens = {t for t in self._tokens(b_norm) if t not in self.stop_tokens}
        if not a_tokens or not b_tokens:
            return 0.0

        inter = len(a_tokens & b_tokens)
        union = len(a_tokens | b_tokens)
        return inter / union if union else 0.0

    def _score_candidate(
        self,
        entity_name: str,
        candidate: Dict[str, Any],
        mapped_class: str,
        description: str = "",
    ) -> float:
        label = self._candidate_label(candidate)
        cand_desc = self._candidate_description(candidate)

        score = 0.0

        name_sim = self._text_similarity(entity_name, label)
        score += name_sim * 0.7

        if description and cand_desc:
            desc_sim = self._text_similarity(description, cand_desc)
            score += desc_sim * 0.2

        # Ajustes suaves por tipo esperado
        low_desc = self._norm_low(cand_desc)
        if mapped_class == "event" and any(k in low_desc for k in ["festival", "holiday", "event", "fiesta"]):
            score += 0.1
        elif mapped_class == "place" and any(k in low_desc for k in ["municipal building", "cathedral", "church", "museum", "palace", "square", "park", "route", "town hall"]):
            score += 0.1
        elif mapped_class == "concept" and any(k in low_desc for k in ["concept", "tradition", "cultural practice"]):
            score += 0.05

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Public linking API
    # ------------------------------------------------------------------

    def resolve(
        self,
        entity_name: Optional[str] = None,
        entity_class: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
        source_url: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        name = self._clean_name(entity_name or kwargs.get("name") or "")
        description = self._norm(long_description or short_description or kwargs.get("description") or "")

        mapped_class = self._map_class_for_search(
            entity_class=entity_class,
            entity_name=name,
            description=description,
        )

        if self.debug:
            print("\n=== DEBUG WIKIDATA INPUT ===")
            print(f"NAME: {name}")
            print(f"CLASS: {entity_class}")
            print(f"ALIASES: {[name] if name else []}")
            print(f"MAPPED CLASS: {mapped_class}")

        if not self._is_queryable_name(name):
            if self.debug:
                print(f"CANDIDATES for {name}: 0")
                print("BEST SCORE: 0.0")
                print("BEST CANDIDATE: None")
            return {
                "wikidata_id": "",
                "qid": "",
                "score": 0.0,
                "candidate": None,
                "mapped_class": mapped_class,
                "candidates": [],
            }

        candidates = self._search_candidates(name, limit=5)

        scored_candidates: List[Dict[str, Any]] = []
        best_qid = ""
        best_score = 0.0
        best_candidate = None

        for cand in candidates:
            qid = cand.get("id") or ""
            if not qid:
                continue

            score = self._score_candidate(
                entity_name=name,
                candidate=cand,
                mapped_class=mapped_class,
                description=description,
            )

            cand_copy = dict(cand)
            cand_copy["score"] = score
            scored_candidates.append(cand_copy)

            if score > best_score:
                best_score = score
                best_qid = qid
                best_candidate = cand_copy

        scored_candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)

        if self.debug:
            print(f"CANDIDATES for {name}: {len(scored_candidates)}")
            print(f"BEST SCORE: {best_score}")
            print(f"BEST CANDIDATE: {best_qid or None}")

        # Umbral conservador
        accepted_qid = best_qid if best_score >= 0.53 else ""

        return {
            "wikidata_id": accepted_qid,
            "qid": accepted_qid,
            "score": best_score,
            "candidate": best_candidate,
            "mapped_class": mapped_class,
            "candidates": scored_candidates,
        }

    def link(
        self,
        entity_name: Optional[str] = None,
        entity_class: Optional[str] = None,
        short_description: Optional[str] = None,
        long_description: Optional[str] = None,
        source_url: Optional[str] = None,
        **kwargs,
    ) -> str:
        result = self.resolve(
            entity_name=entity_name,
            entity_class=entity_class,
            short_description=short_description,
            long_description=long_description,
            source_url=source_url,
            **kwargs,
        )
        return result.get("wikidata_id", "") or ""

    def link_entity(self, *args, **kwargs) -> str:
        return self.link(*args, **kwargs)

    def run(self, *args, **kwargs) -> Dict[str, Any]:
        return self.resolve(*args, **kwargs)

    def process(self, *args, **kwargs) -> Dict[str, Any]:
        return self.resolve(*args, **kwargs)