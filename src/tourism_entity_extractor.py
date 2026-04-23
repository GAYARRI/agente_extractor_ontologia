from __future__ import annotations

import re
from typing import Any, Dict, List


class TourismEntityExtractor:
    """
    Extractor turístico más tolerante con títulos de eventos y POIs,
    pero todavía conservador frente a navegación/UI.

    Soporta bloques:
    - string
    - dict
    - list
    - tuple
    """

    def __init__(self):
        # Patrones base:
        # 1) entidades ancladas por tipo turístico
        # 2) títulos capitalizados de 2 a 8 tokens
        # 3) eventos comunes aunque mezclen minúsculas/stopwords
        self.patterns = [
            re.compile(
                r"\b(?:Museo|Iglesia|Capilla|Catedral|Basílica|Basilica|Castillo|Alcázar|Alcazar|Plaza|Ayuntamiento|Estadio|Hotel|Restaurante|Monasterio|Convento|Palacio|Torre|Puente|Parque|Jardín|Jardin|Barrio|Mercado|Centro|Ruta|Camino|Murallas|Ciudadela|Archivo|Teatro|Auditorio|Sala|Casa)\b(?:\s+(?:de|del|la|las|el|los|y|e|[A-ZÁÉÍÓÚÑ][^\s,;:.!?()\[\]{}]{1,25})){0,10}",
                flags=re.UNICODE,
            ),
            re.compile(
                r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+){1,7}\b",
                flags=re.UNICODE,
            ),
            re.compile(
                r"\b(?:Festival|Concierto|Taller|Mercado|Feria|Exposición|Exposicion|Ciclo|Función|Funcion|Encuentro|Jornada|Jornadas|Visita|Visitas|Ruta|Rutas|Navidad|San Ferm[ií]n)\b(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñü0-9'’\-]+){0,10}",
                flags=re.UNICODE,
            ),
        ]

        self.bad_exact = {
            "día mundial",
            "dia mundial",
            "el día mundial",
            "el dia mundial",
            "semana santa",
            "qué hacer",
            "que hacer",
            "qué ver",
            "que ver",
            "más información",
            "mas informacion",
            "leer más",
            "leer mas",
            "declarado patrimonio cultural inmaterial",
            "todos los derechos reservados",
            "área profesional",
            "area profesional",
            "convention bureau",
            "reserva tu",
            "ir al contenido",
        }

        self.bad_single_words = {
            "conociendo",
            "descubre",
            "historia",
            "información",
            "informacion",
            "visita",
            "visitas",
            "guía",
            "guia",
            "datos",
            "detalle",
            "detalles",
            "contenido",
            "inicio",
            "servicios",
            "actividades",
            "cultura",
            "turismo",
            "agenda",
            "familia",
            "planes",
            "ocio",
            "curiosidades",
            "declarado",
            "mapas",
            "guías",
            "guias",
            "contacto",
            "blog",
            "noticias",
        }

        self.bad_prefixes = (
            "día ",
            "dia ",
            "el día ",
            "el dia ",
            "semana ",
            "celebra ",
            "disfruta ",
            "descubre ",
            "conoce ",
            "historia de ",
            "declarado ",
            "declarada ",
            "todos los ",
            "todas las ",
            "reserva tu ",
            "ir al contenido ",
        )

        self.bad_contains = (
            "google analytics",
            "todos los derechos reservados",
            "convention bureau",
            "área profesional",
            "area profesional",
            "reserva tu",
            "ir al contenido",
            "copiar dirección",
            "copiar direccion",
            "abrir en google maps",
            "sitio web",
            "contacto",
            "política de cookies",
            "politica de cookies",
            "política de privacidad",
            "politica de privacidad",
            "declaración de accesibilidad",
            "declaracion de accesibilidad",
            "aviso legal",
        )

        self.anchor_words = {
            "museo",
            "iglesia",
            "capilla",
            "catedral",
            "basílica",
            "basilica",
            "castillo",
            "alcázar",
            "alcazar",
            "plaza",
            "ayuntamiento",
            "estadio",
            "hotel",
            "restaurante",
            "monasterio",
            "convento",
            "palacio",
            "torre",
            "puente",
            "parque",
            "jardín",
            "jardin",
            "barrio",
            "mercado",
            "centro",
            "festival",
            "concierto",
            "taller",
            "feria",
            "exposición",
            "exposicion",
            "ciclo",
            "función",
            "funcion",
            "ruta",
            "rutas",
            "camino",
            "murallas",
            "ciudadela",
            "navidad",
            "pelota",
        }

        self.trailing_cut_tokens = {
            "es", "son", "fue", "fueron", "era", "eran",
            "que", "donde", "cuando", "como", "aunque",
            "uno", "una", "unos", "unas",
            "este", "esta", "estos", "estas",
            "su", "sus", "un", "una",
            "al", "a", "e", "y", "leer",
            "más", "mas", "info", "información", "informacion",
        }

        self.trailing_invalid_endings = {
            "de", "del", "la", "las", "el", "los", "e", "y", "a", "al"
        }

        self.bad_first_words = {
            "en",
            "la",
            "el",
            "los",
            "las",
            "declarado",
            "declarada",
            "todos",
            "todas",
        }

        self.ui_noise_terms = {
            "qué ver", "que ver", "qué hacer", "que hacer", "dónde comer", "donde comer",
            "dónde alojarse", "donde alojarse", "moverse por", "cómo llegar", "como llegar",
            "donde aparcar", "consignas", "mapas y guías", "mapas y guias",
            "planifica tu viaje", "descubre pamplona",
        }

    def _block_to_text(self, block: Any) -> str:
        if block is None:
            return ""

        if isinstance(block, str):
            return block.strip()

        if isinstance(block, dict):
            parts = []
            for key in ("text", "content", "html", "title", "heading"):
                value = block.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
                elif isinstance(value, (list, tuple)):
                    parts.extend(str(x).strip() for x in value if x is not None and str(x).strip())
            return " ".join(parts).strip()

        if isinstance(block, (list, tuple)):
            return " ".join(str(x).strip() for x in block if x is not None and str(x).strip()).strip()

        return str(block).strip()

    def _normalize_entity(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)
        text = text.strip(" ,.;:-|")
        return text

    def _trim_trailing_noise(self, text: str) -> str:
        words = text.split()

        while words and words[-1].lower() in self.trailing_cut_tokens:
            words.pop()
        while words and words[-1].lower() in self.trailing_invalid_endings:
            words.pop()
        while words and words[-1].lower() in self.trailing_cut_tokens:
            words.pop()

        return " ".join(words).strip()

    def _has_repeated_adjacent_word(self, text: str) -> bool:
        words = text.lower().split()
        for i in range(1, len(words)):
            if words[i] == words[i - 1]:
                return True
        return False

    def _has_anchor_word(self, text: str) -> bool:
        low = text.lower()
        return any(word in low for word in self.anchor_words)

    def _looks_like_sentence_fragment(self, text: str) -> bool:
        low = text.lower().strip()
        words = low.split()

        if len(words) >= 5:
            bad_starts = {
                "de", "del", "la", "las", "el", "los", "y", "o",
                "si", "no", "como", "cuando", "donde", "qué", "que",
                "actividad", "descubre", "encuentra", "reserva",
                "comer", "alojarse", "moverse",
            }
            if words[0] in bad_starts:
                return True

        narrative_tokens = {
            "ofrece", "esconde", "permanece", "permanecen", "invitamos",
            "podrán", "podran", "puedes", "pueden", "combina", "cuenta",
            "descubrir", "explorar", "recorrer", "disfrutar", "programando",
            "sabores", "actividad", "equipaje",
        }
        if any(w in narrative_tokens for w in words):
            return True

        return False

    def _is_mixed_case_fragment(self, text: str) -> bool:
        words = text.split()
        if len(words) < 4:
            return False

        capitalized = sum(1 for w in words if w[:1].isupper())
        lowercase = sum(1 for w in words if w[:1].islower())
        return capitalized >= 1 and lowercase >= 3 and not self._has_anchor_word(text)

    def _is_valid_candidate(self, text: str) -> bool:
        if not text:
            return False

        text = text.strip()
        low = text.lower()
        words = low.split()

        if len(text) < 4:
            return False
        if len(words) > 12:
            return False
        if re.fullmatch(r"[\W\d_]+", text):
            return False
        if self._has_repeated_adjacent_word(text):
            return False
        if low in self.bad_exact:
            return False
        if len(words) == 1 and low in self.bad_single_words:
            return False
        if any(low.startswith(prefix) for prefix in self.bad_prefixes):
            return False
        if any(fragment in low for fragment in self.bad_contains):
            return False
        if low in self.ui_noise_terms:
            return False
        if low.endswith((" es", " son", " fue", " era", " que", " donde", " como")):
            return False
        if words and words[-1] in self.trailing_invalid_endings:
            return False
        if words and words[0] in self.bad_first_words and not self._has_anchor_word(low):
            return False
        if self._looks_like_sentence_fragment(text):
            return False
        if self._is_mixed_case_fragment(text):
            return False

        # Un único token solo si es muy buen ancla turística conocida
        if len(words) == 1:
            return low in {"ciudadela", "catedral", "ayuntamiento", "navidad"}

        # Dos tokens: pedir capitalización o ancla clara
        if len(words) == 2 and not self._has_anchor_word(low):
            raw_words = text.split()
            if not all(w[:1].isupper() for w in raw_words):
                return False

        return True

    def _candidate_from_match(self, entity_text: str, source_text: str) -> Dict[str, Any]:
        return {
            "entity": entity_text,
            "entity_name": entity_text,
            "label": entity_text,
            "name": entity_text,
            "class": "Thing",
            "type": "Thing",
            "score": 0.5,
            "source_text": source_text[:500],
        }

    def extract(self, blocks: List[Any]) -> List[Dict[str, Any]]:
        entities: List[Dict[str, Any]] = []
        seen = set()

        for block in blocks or []:
            text = self._block_to_text(block)
            if not text:
                continue

            for pattern in self.patterns:
                matches = pattern.findall(text)
                for match in matches:
                    entity_text = self._normalize_entity(match)
                    entity_text = self._trim_trailing_noise(entity_text)

                    if not self._is_valid_candidate(entity_text):
                        continue

                    key = entity_text.lower()
                    if key in seen:
                        continue

                    seen.add(key)
                    entities.append(self._candidate_from_match(entity_text, text))

        return entities
