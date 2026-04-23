from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


class EntityFilter:
    """
    Filtro conservador previo al ranking.

    Debe:
    - eliminar ruido evidente de UI, navegación y fragmentos narrativos
    - dejar pasar entidades turísticas plausibles aunque aún estén incompletas
    - no asumir categorías no turísticas como Person
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

        self.ui_terms = {
            "ir al contenido",
            "reserva tu actividad",
            "todos los derechos reservados",
            "accesibilidad",
            "guías convention bureau",
            "guias convention bureau",
            "área profesional",
            "area profesional",
            "ver más",
            "ver mas",
            "leer más",
            "leer mas",
            "mostrar más",
            "mostrar mas",
            "google maps",
            "copiar dirección",
            "copiar direccion",
            "contacto",
            "newsletter",
            "suscríbete",
            "suscribete",
            "apúntate",
            "apuntate",
            "mapas",
        }

        self.navigation_terms = {
            "inicio",
            "home",
            "siguiente",
            "anterior",
            "breadcrumb",
            "menú",
            "menu",
            "volver",
            "subir",
            "todos los lugares",
            "qué ver",
            "que ver",
            "qué hacer",
            "que hacer",
            "dónde alojarse",
            "donde alojarse",
            "dónde comer",
            "donde comer",
            "descubre pamplona",
            "planifica tu viaje",
            "moverse por pamplona",
        }

        self.generic_terms = {
            "agenda",
            "programa",
            "experiencias",
            "familias",
            "viajar",
            "vista",
            "aquí",
            "aqui",
            "además",
            "ademas",
            "locales",
            "lugares",
            "actividad",
            "actividades",
            "preguntas frecuentes",
            "noticias",
        }

        self.instance_terms = {
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
            "jardín",
            "jardin",
            "teatro",
            "puente",
            "festival",
            "feria",
            "congreso",
            "camino",
            "ruta",
            "sendero",
            "frontón",
            "fronton",
            "baluarte",
            "hotel",
            "hostal",
            "albergue",
            "camping",
            "balneario",
            "centro de interpretación",
            "centro de interpretacion",
            "centro de acogida",
            "ciudadela",
            "archivo real",
            "caballo blanco",
            "plaza del castillo",
        }

        self.soft_person_particles = {
            "de", "del", "la", "las", "los", "y",
            "san", "santa", "santo"
        }

        self.verb_markers = {
            "es", "son", "fue", "fueron", "ser", "hay",
            "combina", "combinan", "ofrece", "ofrecen",
            "permite", "permiten", "comenzaremos", "comenzará", "comenzara",
            "visitaremos", "llegaremos", "disfruta", "disfrutar",
            "tiene", "tienen", "puede", "pueden", "ocurre", "ocurren",
            "data", "incluye", "incluyen", "vivir",
            "piensa", "piensan", "transforma", "transforman",
        }

        self.phrase_openers = {
            "a quien", "aquí", "aqui", "si quieres", "si estás", "si estas",
            "cuando", "cuándo", "como", "cómo", "por supuesto",
            "también", "tambien", "además", "ademas",
            "no hay", "no te", "te invitamos",
        }

        self.trailing_noise_tokens = {
            "también", "tambien", "comenzaremos", "comenzará", "comenzara",
            "ver", "más", "mas", "monumento", "monumentos",
            "espacios", "museo", "museos", "lugar", "lugares",
            "pago", "recomendado",
        }

        self.leading_noise_tokens = {
            "actividad", "agenda", "programa", "experiencias",
            "por", "por supuesto", "también", "tambien",
        }

        self.false_positive_patterns = [
            r"\bmultitud de actividades\b",
            r"\bgran variedad de\b",
            r"\bmejor manera de\b",
            r"\bcalidad de vida\b",
            r"\bservicio integral de\b",
            r"\btratamientos de\b",
            r"\bgastronom[ií]a de alta calidad\b",
            r"\bcentros de investigaci[oó]n\b",
            r"\benvolturas de fango\b",
            r"\bpamplona agenda\b",
            r"\bagenda multitud\b",
            r"\bactividad san ferm[ií]n\b",
            r"\bpor supuesto san ferm[ií]n\b",
            r"\bqu[ií]en fue san ferm[ií]n\b",
            r"\bsan ferm[ií]n es mucho m[aá]s\b",
            r"\bcatedral hotel\b",
        ]

    # ---------------------------------------------------------
    # utils
    # ---------------------------------------------------------

    def _norm(self, value: Any) -> str:
        value = "" if value is None else str(value)
        value = value.strip()
        value = re.sub(r"\s+", " ", value)
        return value

    def _low(self, value: Any) -> str:
        return self._norm(value).lower()

    def _strip_accents(self, text: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )

    def _low_ascii(self, value: Any) -> str:
        return self._strip_accents(self._low(value))

    def _tokenize(self, text: str) -> List[str]:
        return [t for t in re.split(r"[^\wáéíóúñü]+", self._low(text)) if t]

    def _short_type(self, value: Any) -> str:
        raw = self._norm(value)
        if not raw:
            return ""
        return raw.split("#")[-1].split("/")[-1].strip()

    def _entity_name(self, entity: Dict[str, Any]) -> str:
        return self._norm(
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        )

    def _entity_class(self, entity: Dict[str, Any]) -> str:
        return self._short_type(entity.get("class") or entity.get("type") or "")

    def _clean_name_edges(self, text: str) -> str:
        value = self._norm(text)

        changed = True
        while changed and value:
            changed = False
            low = self._low(value)

            for prefix in sorted(self.leading_noise_tokens, key=len, reverse=True):
                if low.startswith(prefix + " "):
                    value = self._norm(value[len(prefix):])
                    changed = True
                    break

            if changed:
                continue

            low = self._low(value)
            tokens = value.split()
            if tokens:
                last = self._low(tokens[-1])
                if last in self.trailing_noise_tokens:
                    value = self._norm(" ".join(tokens[:-1]))
                    changed = True

        return value.strip(" -|,;:")

    # ---------------------------------------------------------
    # weak signals
    # ---------------------------------------------------------

    def _looks_like_person_name(self, text: str) -> bool:
        """
        Señal débil.
        No implica rechazo automático porque muchos nombres de persona
        terminan siendo esculturas, retratos, monumentos, calles, etc.
        """
        name = self._norm(text)
        parts = [p for p in re.split(r"\s+", name) if p]
        if len(parts) < 2 or len(parts) > 4:
            return False

        properish = 0
        for p in parts:
            p_clean = p.strip(".,;:¡!¿?()[]{}\"'")
            if not p_clean:
                continue
            if self._low(p_clean) in self.soft_person_particles:
                continue
            if re.match(r"^[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü\-]+$", p_clean):
                properish += 1

        return properish >= 2

    def _has_instance_signal(self, text: str) -> bool:
        low = self._low(text)
        return any(term in low for term in self.instance_terms)

    def _has_supportive_context(self, text: str, context: str) -> bool:
        merged = f"{self._low(text)} || {self._low(context)}"
        return any(term in merged for term in self.instance_terms)

    def _looks_like_event_signal(self, text: str, context: str = "") -> bool:
        merged = f"{self._low(text)} || {self._low(context)}"
        event_terms = {
            "festival", "feria", "congreso", "evento",
            "san fermín", "san fermin", "punto de vista",
            "ecozine", "jotas", "flamenco on fire",
        }
        return any(term in merged for term in event_terms)

    def _looks_like_route_signal(self, text: str, context: str = "") -> bool:
        merged = f"{self._low(text)} || {self._low(context)}"
        route_terms = {
            "camino de santiago", "ruta", "sendero",
            "itinerario", "recorrido", "peregrinación", "peregrinacion",
        }
        return any(term in merged for term in route_terms)

    # ---------------------------------------------------------
    # hard rejections
    # ---------------------------------------------------------

    def _is_ui_fragment(self, name: str) -> bool:
        low = self._low_ascii(name)
        for term in self.ui_terms:
            if self._strip_accents(term) in low:
                return True
        return False

    def _is_navigation_fragment(self, name: str) -> bool:
        low = self._low_ascii(name)
        for term in self.navigation_terms:
            if self._strip_accents(term) in low:
                return True
        return False

    def _is_false_positive_pattern(self, name: str) -> bool:
        low = self._low(name)
        return any(re.search(p, low, flags=re.IGNORECASE) for p in self.false_positive_patterns)

    def _is_phrase_fragment(self, name: str) -> bool:
        low = self._low(name)
        tokens = self._tokenize(name)

        if not tokens:
            return True

        if len(tokens) >= 6:
            return True

        if any(low.startswith(opener) for opener in self.phrase_openers):
            return True

        if len(tokens) >= 4 and any(t in self.verb_markers for t in tokens):
            return True

        if re.search(r"\b(qu[ií]en|c[oó]mo|cu[aá]ndo)\b", low):
            return True

        return False

    def _is_overgeneric(self, name: str) -> bool:
        low = self._low(name)
        if low in self.generic_terms:
            return True
        if low in self.navigation_terms:
            return True
        if low in self.ui_terms:
            return True
        return False

    def _is_bad_compound(self, name: str) -> bool:
        low = self._low(name)
        tokens = self._tokenize(name)

        generic_hits = 0
        for token in tokens:
            if token in {
                "agenda", "actividad", "actividades", "experiencias",
                "lugares", "lugar", "monumento", "monumentos", "museo",
                "museos", "espacios", "ver", "más", "mas", "programa"
            }:
                generic_hits += 1

        if len(tokens) >= 5 and generic_hits >= 2:
            return True

        if len(tokens) >= 7:
            return True

        if re.search(r"\b(ver|más|mas|comenzaremos|también|tambien)\b", low):
            return True

        return False

    # ---------------------------------------------------------
    # scoring
    # ---------------------------------------------------------

    def _score_entity_name(
        self,
        name: str,
        context: str = "",
        entity_class: str = "",
        expected_type: Optional[str] = None,
    ) -> Tuple[int, List[str]]:
        reasons: List[str] = []
        score = 0

        clean_name = self._clean_name_edges(name)
        low = self._low(clean_name)
        tokens = self._tokenize(clean_name)
        entity_class_low = self._low(entity_class)

        if not clean_name:
            return -10, ["empty_name"]

        if self._is_ui_fragment(clean_name):
            return -8, ["ui_fragment"]

        if self._is_navigation_fragment(clean_name):
            return -8, ["foreign_noise"]

        if self._is_false_positive_pattern(clean_name):
            return -8, ["phrase_fragment"]

        if self._is_phrase_fragment(clean_name):
            return -8, ["phrase_fragment"]

        if self._is_overgeneric(clean_name):
            score -= 4
            reasons.append("generic_name")

        if len(tokens) == 1:
            score -= 2
            reasons.append("single_token")

        if len(tokens) >= 2:
            score += 1
            reasons.append("multiword_name")

        if self._has_instance_signal(clean_name):
            score += 3
            reasons.append("instance_indicator")

        if self._has_supportive_context(clean_name, context):
            score += 2
            reasons.append("supportive_context")

        if self._looks_like_event_signal(clean_name, context):
            score += 2
            reasons.append("event_lexical_hint")

        if self._looks_like_route_signal(clean_name, context):
            score += 2
            reasons.append("route_lexical_hint")

        if self._looks_like_person_name(clean_name):
            score += 1
            reasons.append("person_name_weak_signal")

        if entity_class_low in {
            "cathedral", "church", "chapel", "basilica", "castle",
            "alcazar", "palace", "museum", "townhall", "square",
            "park", "garden", "route", "event", "market", "stadium",
            "monument"
        }:
            score += 2
            reasons.append("strong_type")

        if expected_type:
            if self._low(expected_type) == entity_class_low and entity_class_low:
                score += 1
                reasons.append("expected_type_match")

        if self._is_bad_compound(clean_name):
            score -= 5
            reasons.append("bad_compound_name")

        # Un nombre de persona sin soporte contextual/instancia no debe subir mucho
        if self._looks_like_person_name(clean_name) and not self._has_instance_signal(clean_name):
            if not self._has_supportive_context(clean_name, context):
                score -= 1

        return score, reasons

    # ---------------------------------------------------------
    # public api
    # ---------------------------------------------------------

    def filter(
        self,
        entities: Iterable[Dict[str, Any]],
        context_getter: Optional[Callable[[Dict[str, Any]], str]] = None,
        page_signals: Optional[Dict[str, Any]] = None,
        expected_type: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        kept: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)
            raw_name = self._entity_name(item)
            clean_name = self._clean_name_edges(raw_name)

            item["name"] = clean_name or raw_name
            item["entity_name"] = clean_name or raw_name
            item["label"] = clean_name or raw_name
            item["entity"] = clean_name or raw_name

            context = ""
            if callable(context_getter):
                try:
                    context = context_getter(item) or ""
                except Exception:
                    context = ""

            entity_class = self._entity_class(item)

            score, reasons = self._score_entity_name(
                clean_name or raw_name,
                context=context,
                entity_class=entity_class,
                expected_type=expected_type,
            )

            decision = "keep"
            reject_reasons: List[str] = []

            if score <= -3:
                decision = "reject"
                reject_reasons = [r for r in reasons if r in {
                    "ui_fragment", "foreign_noise", "phrase_fragment",
                    "generic_name", "single_token", "bad_compound_name"
                }]
                if not reject_reasons:
                    reject_reasons = ["low_score"]

            audit = {
                "decision": decision,
                "score": score,
                "reasons": reject_reasons if decision == "reject" else reasons,
            }
            item["filter_audit"] = audit

            if decision == "keep":
                kept.append(item)
            else:
                rejected.append(item)

        if self.debug:
            print(f"[DEBUG FILTER] kept={len(kept)} rejected={len(rejected)}")
            for sample in rejected[:10]:
                try:
                    print(
                        f"[DEBUG REJECT SAMPLE] {sample.get('name')} {sample.get('filter_audit')}"
                    )
                except Exception:
                    pass

        return kept, rejected