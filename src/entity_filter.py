from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


class EntityFilter:
    """
    Conservative pre-ranking filter.

    The goal is to remove obvious UI noise and sentence fragments without
    discarding valid tourism entities that appear inside editorial pages.
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

        self.ui_terms = {
            "ir al contenido",
            "reserva tu actividad",
            "todos los derechos reservados",
            "accesibilidad",
            "guias convention bureau",
            "area profesional",
            "ver mas",
            "leer mas",
            "mostrar mas",
            "google maps",
            "copiar direccion",
            "contacto",
            "newsletter",
            "suscribete",
            "apuntate",
            "mapas",
        }

        self.navigation_terms = {
            "inicio",
            "home",
            "siguiente",
            "anterior",
            "breadcrumb",
            "menu",
            "volver",
            "subir",
            "todos los lugares",
            "que ver",
            "que hacer",
            "donde alojarse",
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
            "aqui",
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
            "basilica",
            "capilla",
            "monasterio",
            "convento",
            "castillo",
            "alcazar",
            "palacio",
            "museo",
            "mercado",
            "plaza",
            "parque",
            "jardin",
            "teatro",
            "auditorio",
            "puente",
            "festival",
            "feria",
            "congreso",
            "camino",
            "ruta",
            "sendero",
            "fronton",
            "baluarte",
            "hotel",
            "hostal",
            "albergue",
            "camping",
            "balneario",
            "centro de interpretacion",
            "centro de acogida",
            "ciudadela",
            "archivo real",
            "caballo blanco",
            "plaza del castillo",
            "acuario",
            "oficina de turismo",
            "estacion de tren",
            "estacion de autobuses",
            "parque natural",
            "espacio",
        }

        self.soft_person_particles = {"de", "del", "la", "las", "los", "y", "san", "santa", "santo"}

        self.verb_markers = {
            "es", "son", "fue", "fueron", "ser", "hay",
            "combina", "combinan", "ofrece", "ofrecen",
            "permite", "permiten", "comenzaremos", "comenzara",
            "visitaremos", "llegaremos", "disfruta", "disfrutar",
            "tiene", "tienen", "puede", "pueden", "ocurre", "ocurren",
            "data", "incluye", "incluyen", "vivir",
            "piensa", "piensan", "transforma", "transforman",
        }

        self.phrase_openers = {
            "a quien", "aqui", "si quieres", "si estas",
            "cuando", "como", "por supuesto",
            "tambien", "ademas", "no hay", "no te", "te invitamos",
        }

        self.trailing_noise_tokens = {
            "tambien", "comenzaremos", "comenzara",
            "ver", "mas", "monumento", "monumentos",
            "espacios", "museo", "museos", "lugar", "lugares",
            "pago", "recomendado", "precio", "precios",
        }

        self.leading_noise_tokens = {
            "actividad", "agenda", "programa", "experiencias", "por", "por supuesto", "tambien",
        }

        self.false_positive_patterns = [
            r"\bmultitud de actividades\b",
            r"\bgran variedad de\b",
            r"\bmejor manera de\b",
            r"\bcalidad de vida\b",
            r"\bservicio integral de\b",
            r"\btratamientos de\b",
            r"\bgastronomia de alta calidad\b",
            r"\bcentros de investigacion\b",
            r"\benvolturas de fango\b",
            r"\bpamplona agenda\b",
            r"\bagenda multitud\b",
            r"\bactividad san fermin\b",
            r"\bpor supuesto san fermin\b",
            r"\bquien fue san fermin\b",
            r"\bsan fermin es mucho mas\b",
            r"\bcatedral hotel\b",
            r"^ayuntamiento de pamplona (casco antiguo|pump track|frente ciudadela|san fermin|estrellas michelin|queso|alojamientos|verde|reserva|preguntas|mercados|agroturismos|cordero|menestra|patxaran|actas|pimientos|ajoarriero|trucha|pochas|esparragos|cuajada|chistorra|goxua|pantxineta|fritos|planes|cultura)\b",
            r"^ayuntamiento de pamplona (hoteles|restaurantes|campings|albergues|pensiones|paseos|excursiones|categorias|noticias|blog|familias|grupos|juegos|senderismo|horario|eurovelo|sidrerias|consigna|solicitud|pelota|parques|individual|planifica)\b",
        ]

        self.technical_noise_terms = {
            "tecnologia",
            "tecnologias",
            "agroalimentaria",
            "agroalimentarias",
            "infraestructura",
            "infraestructuras",
            "investigacion",
            "innovacion",
            "desarrollo",
            "biotecnologia",
            "laboratorio",
            "industrial",
            "agronomica",
            "agronomicas",
        }

        self.category_like_terms = {
            "visitas guiadas",
            "actividades",
            "actividad",
            "culturales",
            "rutas",
            "eventos",
            "gastronomia",
            "postres",
            "excursiones desde",
            "para todos",
            "para jovenes",
            "para jóvenes",
            "restaurantes",
            "hoteles",
            "mercados",
            "albergues",
            "campings",
            "pensiones y hostales",
            "areas de autocaravanas",
            "áreas de autocaravanas",
            "paseos y rutas",
            "todas las noticias",
            "todos los lugares",
            "categorias",
            "categorías",
            "donde comer",
            "dónde comer",
            "planifica tu viaje",
        }

        self.theme_like_terms = {
            "sostenibilidad turistica",
            "sostenibilidad turística",
            "produccion agraria",
            "producción agraria",
            "interes turistico internacional",
            "interés turístico internacional",
            "turismo responsable",
            "desarrollo sostenible",
        }

    def _norm(self, value: Any) -> str:
        value = "" if value is None else str(value)
        value = value.strip()
        return re.sub(r"\s+", " ", value)

    def _low(self, value: Any) -> str:
        return self._norm(value).lower()

    def _strip_accents(self, text: str) -> str:
        return "".join(
            char for char in unicodedata.normalize("NFD", text)
            if unicodedata.category(char) != "Mn"
        )

    def _low_ascii(self, value: Any) -> str:
        return self._strip_accents(self._low(value))

    def _tokenize(self, text: str) -> List[str]:
        return [token for token in re.split(r"[^\wáéíóúñü]+", self._low(text)) if token]

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

            tokens = value.split()
            if tokens and self._low(tokens[-1]) in self.trailing_noise_tokens:
                value = self._norm(" ".join(tokens[:-1]))
                changed = True

        return value.strip(" -|,;:")

    def _looks_like_person_name(self, text: str) -> bool:
        name = self._norm(text)
        parts = [part for part in re.split(r"\s+", name) if part]
        if len(parts) < 2 or len(parts) > 4:
            return False

        properish = 0
        for part in parts:
            cleaned = part.strip(".,;:!?()[]{}\"'")
            if not cleaned:
                continue
            if self._low(cleaned) in self.soft_person_particles:
                continue
            if re.match(r"^[A-ZÁÉÍÓÚÑ][a-záéíóúñü\-]+$", cleaned):
                properish += 1
        return properish >= 2

    def _has_instance_signal(self, text: str) -> bool:
        low = self._low_ascii(text)
        return any(term in low for term in self.instance_terms)

    def _has_supportive_context(self, text: str, context: str) -> bool:
        merged = f"{self._low_ascii(text)} || {self._low_ascii(context)}"
        return any(term in merged for term in self.instance_terms)

    def _looks_like_event_signal(self, text: str, context: str = "") -> bool:
        merged = f"{self._low_ascii(text)} || {self._low_ascii(context)}"
        event_terms = {
            "festival", "feria", "congreso", "evento",
            "san fermin", "punto de vista", "ecozine", "jotas", "flamenco on fire",
        }
        return any(term in merged for term in event_terms)

    def _looks_like_route_signal(self, text: str, context: str = "") -> bool:
        merged = f"{self._low_ascii(text)} || {self._low_ascii(context)}"
        route_terms = {
            "camino de santiago", "ruta", "sendero", "itinerario", "recorrido", "peregrinacion",
        }
        return any(term in merged for term in route_terms)

    def _is_ui_fragment(self, name: str) -> bool:
        low = self._low_ascii(name)
        return any(term in low for term in self.ui_terms)

    def _is_navigation_fragment(self, name: str) -> bool:
        low = self._low_ascii(name)
        return any(term in low for term in self.navigation_terms)

    def _is_false_positive_pattern(self, name: str) -> bool:
        low = self._low_ascii(name)
        return any(re.search(pattern, low, flags=re.IGNORECASE) for pattern in self.false_positive_patterns)

    def _is_phrase_fragment(self, name: str) -> bool:
        low = self._low_ascii(name)
        tokens = self._tokenize(name)
        if not tokens:
            return True

        if len(tokens) >= 9 and not self._has_instance_signal(name):
            return True
        if any(low.startswith(opener) for opener in self.phrase_openers):
            return True
        if len(tokens) >= 5 and any(token in self.verb_markers for token in tokens) and not self._has_instance_signal(name):
            return True
        if re.search(r"\b(quien|como|cuando)\b", low):
            return True
        return False

    def _is_overgeneric(self, name: str) -> bool:
        low = self._low_ascii(name)
        return low in self.generic_terms or low in self.navigation_terms or low in self.ui_terms

    def _is_bad_compound(self, name: str) -> bool:
        low = self._low_ascii(name)
        tokens = self._tokenize(name)
        generic_hits = sum(
            1
            for token in tokens
            if token in {"agenda", "actividad", "actividades", "experiencias", "lugares", "lugar", "espacios", "ver", "mas", "programa"}
        )

        if len(tokens) >= 6 and generic_hits >= 2 and not self._has_instance_signal(name):
            return True
        if len(tokens) >= 9 and not self._has_instance_signal(name):
            return True
        if re.search(r"\b(ver|mas|comenzaremos|tambien)\b", low) and not self._has_instance_signal(name):
            return True
        return False

    def _looks_like_technical_fragment(self, name: str, context: str = "") -> bool:
        merged = f"{self._low_ascii(name)} || {self._low_ascii(context)}"
        if self._has_instance_signal(name):
            return False

        hits = sum(1 for term in self.technical_noise_terms if term in merged)
        if hits >= 2:
            return True

        if any(term in self._low_ascii(name) for term in self.technical_noise_terms):
            return True

        return False

    def _looks_like_category_fragment(self, name: str, context: str = "") -> bool:
        low = self._low_ascii(name)
        merged = f"{low} || {self._low_ascii(context)}"
        if self._has_instance_signal(name):
            return False

        if low in self.category_like_terms or low in self.theme_like_terms:
            return True

        if any(term in low for term in self.theme_like_terms):
            return True

        if any(term in low for term in self.category_like_terms):
            if len(low.split()) <= 4:
                return True

        noisy_pairings = [
            ("actividades", "skate"),
            ("actividades", "pump track"),
            ("culturales", "visitas"),
            ("postres", "queso roncal"),
            ("ayuntamiento de pamplona", "hoteles"),
            ("ayuntamiento de pamplona", "restaurantes"),
            ("ayuntamiento de pamplona", "mercados"),
            ("ayuntamiento de pamplona", "excursiones"),
            ("ayuntamiento de pamplona", "albergues"),
        ]
        return any(a in merged and b in merged for a, b in noisy_pairings)

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
        tokens = self._tokenize(clean_name)
        entity_class_low = self._low_ascii(entity_class)

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
        if self._looks_like_technical_fragment(clean_name, context):
            return -8, ["technical_fragment"]
        if self._looks_like_category_fragment(clean_name, context):
            return -8, ["category_fragment"]

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
            "cathedral", "church", "chapel", "basilica", "castle", "alcazar", "palace", "museum",
            "townhall", "square", "park", "garden", "route", "event", "market", "stadium",
            "monument", "bridge", "theater", "auditorium", "trainstation", "busstation",
        }:
            score += 2
            reasons.append("strong_type")

        if expected_type and self._low_ascii(expected_type) == entity_class_low and entity_class_low:
            score += 1
            reasons.append("expected_type_match")

        if self._is_bad_compound(clean_name):
            score -= 5
            reasons.append("bad_compound_name")

        if self._looks_like_person_name(clean_name) and not self._has_instance_signal(clean_name):
            if not self._has_supportive_context(clean_name, context):
                score -= 1

        return score, reasons

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
            if score <= -4:
                decision = "reject"
                reject_reasons = [
                    reason for reason in reasons
                    if reason in {"ui_fragment", "foreign_noise", "phrase_fragment", "technical_fragment", "category_fragment", "generic_name", "single_token", "bad_compound_name"}
                ]
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
                    print(f"[DEBUG REJECT SAMPLE] {sample.get('name')} {sample.get('filter_audit')}")
                except Exception:
                    pass

        return kept, rejected
