from __future__ import annotations

import re
from typing import Any, Dict, List


class TourismEntityExtractor:
    """
    Extract tourism entities from editorial content and heading-like blocks.

    The extractor is intentionally permissive with page titles and list-like
    paragraphs, while still rejecting obvious UI fragments and noise.
    """

    def __init__(self):
        anchor_heads = (
            "Museo|Iglesia|Capilla|Catedral|Basilica|Castillo|Alcazar|Plaza|Ayuntamiento|"
            "Estadio|Hotel|Restaurante|Monasterio|Convento|Palacio|Torre|Puente|Parque|"
            "Jardin|Barrio|Mercado|Centro|Ruta|Camino|Murallas|Ciudadela|Archivo|Teatro|"
            "Auditorio|Sala|Casa|Oficina|Estacion|Acuario|Espacio|Baluarte|Festival|Feria"
        )
        capital_token = r"[A-ZA-ZÁÉÍÓÚÜÑ][^\s,;:.!?()\[\]{}]{1,25}"
        flexible_token = r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9'’-]+"

        self.patterns = [
            re.compile(
                rf"\b(?:{anchor_heads})\b"
                rf"(?:\s+(?:de|del|la|las|el|los|en|{capital_token})){{0,12}}",
                flags=re.UNICODE,
            ),
            re.compile(
                r"\b(?:Oficina de Turismo|Centro de Interpretacion|Centro de Interpretación|"
                r"Estacion de Tren|Estación de Tren|Estacion de Autobuses|Estación de Autobuses|"
                r"Plaza de Toros|Parque Natural)\b"
                rf"(?:\s+(?:de|del|la|las|el|los|en|{capital_token})){{0,8}}",
                flags=re.UNICODE,
            ),
            re.compile(
                r"\b[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+){1,7}\b",
                flags=re.UNICODE,
            ),
            re.compile(
                rf"\b(?:Festival|Concierto|Taller|Mercado|Feria|Exposicion|Exposición|Ciclo|Funcion|"
                rf"Función|Encuentro|Jornada|Jornadas|Visita|Visitas|Ruta|Rutas|Navidad|San Fermin)\b"
                rf"(?:\s+{flexible_token}){{0,10}}",
                flags=re.UNICODE,
            ),
            re.compile(
                rf"\b(?:Festival|Mercado|Feria|Ruta|Camino)\b"
                rf"(?:\s+{flexible_token}){{2,16}}",
                flags=re.UNICODE,
            ),
        ]

        self.bad_exact = {
            "dia mundial",
            "el dia mundial",
            "semana santa",
            "que hacer",
            "que ver",
            "mas informacion",
            "leer mas",
            "declarado patrimonio cultural inmaterial",
            "todos los derechos reservados",
            "area profesional",
            "convention bureau",
            "reserva tu",
            "ir al contenido",
            "todos los lugares",
            "todas las noticias",
            "categorias",
            "categorías",
            "planifica tu viaje",
        }

        self.bad_single_words = {
            "conociendo",
            "descubre",
            "historia",
            "informacion",
            "visita",
            "visitas",
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
            "guias",
            "contacto",
            "blog",
            "noticias",
        }

        self.bad_prefixes = (
            "dia ",
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
            "categorias ",
            "categorías ",
            "donde comer ",
            "dónde comer ",
            "que ver ",
            "qué ver ",
            "que hacer ",
            "qué hacer ",
        )

        self.bad_contains = (
            "google analytics",
            "todos los derechos reservados",
            "convention bureau",
            "area profesional",
            "reserva tu",
            "ir al contenido",
            "copiar direccion",
            "abrir en google maps",
            "sitio web",
            "contacto",
            "politica de cookies",
            "politica de privacidad",
            "declaracion de accesibilidad",
            "aviso legal",
        )

        self.leading_noise_phrases = (
            "ir al contenido",
            "reserva tu actividad",
            "descubre pamplona",
            "planifica tu viaje",
            "todos los lugares",
            "todas las noticias",
            "categorias",
            "categorías",
            "que ver",
            "qué ver",
            "que hacer",
            "qué hacer",
            "donde comer",
            "dónde comer",
            "pensiones y hostales",
            "albergues",
            "campings",
            "excursiones desde pamplona",
            "paseos y rutas",
            "hoteles",
            "restaurantes",
            "mercados",
        )

        self.anchor_words = {
            "museo",
            "iglesia",
            "capilla",
            "catedral",
            "basilica",
            "castillo",
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
            "jardin",
            "barrio",
            "mercado",
            "centro",
            "oficina",
            "estacion",
            "festival",
            "concierto",
            "taller",
            "feria",
            "exposicion",
            "ciclo",
            "funcion",
            "ruta",
            "rutas",
            "camino",
            "murallas",
            "ciudadela",
            "navidad",
            "pelota",
            "auditorio",
            "acuario",
            "espacio",
            "baluarte",
        }

        self.trailing_cut_tokens = {
            "es", "son", "fue", "fueron", "era", "eran",
            "que", "donde", "cuando", "como", "aunque",
            "uno", "una", "unos", "unas",
            "este", "esta", "estos", "estas",
            "su", "sus", "un", "una",
            "al", "a", "e", "y", "leer",
            "mas", "info", "informacion",
            "precio", "precios", "entrada", "entradas",
            "punto", "finalizacion",
        }

        self.trailing_invalid_endings = {
            "de", "del", "la", "las", "el", "los", "e", "y", "a", "al",
        }

        self.narrative_cut_markers = (
            " agrupa ",
            " regresa ",
            " ofrece ",
            " celebr",
            " tienen lugar ",
            " tiene lugar ",
            " consulta fechas ",
            " el segundo sabado ",
            " los segundos sabados ",
            " gastronomia ",
            " secretos ",
            " deja huella ",
            " se convirtio ",
            " se convirtió ",
            " considerada monumento nacional ",
            " para todos ",
            " para jovenes ",
            " para jóvenes ",
            " excursiones desde ",
        )

        self.bad_first_words = {
            "en", "la", "el", "los", "las", "declarado", "declarada", "todos", "todas",
        }

        self.ui_noise_terms = {
            "que ver", "que hacer", "donde comer", "donde alojarse", "moverse por",
            "como llegar", "donde aparcar", "consignas", "mapas y guias",
            "planifica tu viaje", "descubre pamplona",
        }

        self.category_noise_terms = {
            "visitas guiadas",
            "actividades",
            "culturales visitas",
            "postres queso roncal",
            "produccion agraria ecologica",
            "sostenibilidad turistica",
            "interes turistico internacional",
            "todos los lugares",
            "todas las noticias",
            "categorias",
            "categorías",
            "planifica tu viaje",
        }

        self.list_separators = (";", " · ", " | ")
        self.anchor_split_re = re.compile(
            rf"\s+(?:y|e)\s+(?=(?:el|la|los|las)\s+)?(?:{anchor_heads})\b",
            flags=re.UNICODE,
        )
        self.nested_anchor_re = re.compile(
            r"\b(?:museo|iglesia|capilla|catedral|basilica|castillo|alcazar|plaza|ayuntamiento|"
            r"estadio|hotel|restaurante|monasterio|convento|palacio|torre|puente|parque|jardin|"
            r"barrio|mercado|centro|ruta|camino|murallas|ciudadela|archivo|teatro|auditorio|"
            r"sala|casa|oficina|estacion|acuario|espacio|baluarte|festival|feria)\s+"
            r"(?:de|del|la|las|el|los)\s+",
            flags=re.UNICODE,
        )

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

    def _block_context_signals(self, block: Any) -> Dict[str, Any]:
        if not isinstance(block, dict):
            return {}

        return {
            "tag": block.get("tag") or "",
            "href": block.get("href") or "",
            "class": block.get("class") or "",
            "id": block.get("id") or "",
            "heading": block.get("heading") or "",
            "parent_tag": block.get("parent_tag") or "",
            "parent_class": block.get("parent_class") or "",
            "parent_id": block.get("parent_id") or "",
            "link_text": block.get("link_text") or "",
            "link_href": block.get("link_href") or "",
        }

    def _normalize_entity(self, text: str) -> str:
        text = re.sub(r"\s+", " ", (text or "").strip())
        low = text.lower()

        changed = True
        while changed:
            changed = False
            for phrase in self.leading_noise_phrases:
                if low.startswith(phrase + " "):
                    text = text[len(phrase):].strip()
                    low = text.lower()
                    changed = True
                    break

        return text.strip(" ,.;:-|")

    def _trim_trailing_noise(self, text: str) -> str:
        low = text.lower()
        for marker in self.narrative_cut_markers:
            idx = low.find(marker)
            if idx > 0:
                text = text[:idx].strip()
                low = text.lower()

        words = text.split()
        if len(words) >= 6:
            first_chunk = " ".join(words[:4]).lower()
            for idx in range(4, len(words) - 3):
                chunk = " ".join(words[idx:idx + 4]).lower()
                if chunk == first_chunk:
                    text = " ".join(words[:idx]).strip()
                    words = text.split()
                    break

        words = text.split()

        while words and words[-1].lower() in self.trailing_cut_tokens:
            words.pop()
        while words and words[-1].lower() in self.trailing_invalid_endings:
            words.pop()
        while words and words[-1].lower() in self.trailing_cut_tokens:
            words.pop()

        return " ".join(words).strip()

    def _split_block_candidates(self, text: str) -> List[str]:
        chunks = [text]
        for separator in self.list_separators:
            next_chunks: List[str] = []
            for chunk in chunks:
                next_chunks.extend([part.strip() for part in chunk.split(separator) if part.strip()])
            chunks = next_chunks or chunks

        expanded: List[str] = []
        for chunk in chunks:
            parts = [part.strip() for part in self.anchor_split_re.split(chunk) if part.strip()]
            expanded.extend(parts or [chunk])

        return expanded or chunks

    def _has_repeated_adjacent_word(self, text: str) -> bool:
        words = text.lower().split()
        return any(words[idx] == words[idx - 1] for idx in range(1, len(words)))

    def _has_anchor_word(self, text: str) -> bool:
        low = text.lower()
        return any(word in low for word in self.anchor_words)

    def _looks_like_sentence_fragment(self, text: str) -> bool:
        low = text.lower().strip()
        words = low.split()

        if len(words) >= 6 and not self._has_anchor_word(text):
            bad_starts = {
                "de", "del", "la", "las", "el", "los", "y", "o",
                "si", "no", "como", "cuando", "donde", "que",
                "actividad", "descubre", "encuentra", "reserva",
                "comer", "alojarse", "moverse",
            }
            if words and words[0] in bad_starts:
                return True

        narrative_tokens = {
            "ofrece", "esconde", "permanece", "permanecen", "invitamos",
            "podrian", "podran", "puedes", "pueden", "combina", "cuenta",
            "descubrir", "explorar", "recorrer", "disfrutar", "programando",
            "sabores", "actividad", "equipaje",
        }
        return any(word in narrative_tokens for word in words) and not self._has_anchor_word(text)

    def _is_mixed_case_fragment(self, text: str) -> bool:
        words = text.split()
        if len(words) < 4:
            return False

        capitalized = sum(1 for word in words if word[:1].isupper())
        lowercase = sum(1 for word in words if word[:1].islower())
        return capitalized >= 1 and lowercase >= 3 and not self._has_anchor_word(text)

    def _is_nested_tail_of_anchored_entity(self, text: str, source_text: str) -> bool:
        low = text.lower().strip()
        if self._has_anchor_word(low):
            return False
        if len(low.split()) < 2:
            return False

        escaped = re.escape(low)
        pattern = self.nested_anchor_re.pattern + escaped + r"\b"
        return bool(re.search(pattern, source_text.lower()))

    def _is_shifted_anchor_fragment(self, text: str) -> bool:
        low = text.lower().strip()
        words = low.split()
        if len(words) < 3:
            return False

        if words[0] in {"murallas", "ciudadela"} and any(
            f" {anchor}" in low for anchor in ("festival", "mercado", "feria", "ruta", "camino")
        ):
            return True

        if any(low.startswith(anchor) for anchor in self.anchor_words):
            return False

        return any(f" {anchor}" in low for anchor in self.anchor_words)

    def _is_valid_candidate(self, text: str) -> bool:
        if not text:
            return False

        text = text.strip()
        low = text.lower()
        words = low.split()

        if len(text) < 4:
            return False
        if len(words) > 18:
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
        if low in self.category_noise_terms:
            return False
        if low.startswith("actividades ") or low.startswith("visitas guiadas "):
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
        if self._is_shifted_anchor_fragment(text):
            return False

        if len(words) == 1:
            return low in {"ciudadela", "catedral", "ayuntamiento", "navidad", "baluarte"}

        if len(words) == 2 and not self._has_anchor_word(low):
            raw_words = text.split()
            if not all(word[:1].isupper() for word in raw_words):
                return False

        return True

    def _candidate_from_match(self, entity_text: str, source_text: str, block: Any = None) -> Dict[str, Any]:
        return {
            "entity": entity_text,
            "entity_name": entity_text,
            "label": entity_text,
            "name": entity_text,
            "class": "Thing",
            "type": "Thing",
            "score": 0.5,
            "source_text": source_text[:500],
            "html_context_signals": self._block_context_signals(block),
        }

    def extract(self, blocks: List[Any]) -> List[Dict[str, Any]]:
        entities: List[Dict[str, Any]] = []
        seen = set()

        for block in blocks or []:
            text = self._block_to_text(block)
            if not text:
                continue

            for candidate_text in self._split_block_candidates(text):
                for pattern in self.patterns:
                    for match in pattern.findall(candidate_text):
                        entity_text = self._normalize_entity(match)
                        entity_text = self._trim_trailing_noise(entity_text)

                        if self._is_nested_tail_of_anchored_entity(entity_text, candidate_text):
                            continue
                        if not self._is_valid_candidate(entity_text):
                            continue

                        key = entity_text.lower()
                        if key in seen:
                            continue

                        seen.add(key)
                        entities.append(self._candidate_from_match(entity_text, text, block=block))

        cleaned: List[Dict[str, Any]] = []
        for item in sorted(entities, key=lambda x: len(str(x.get("name", ""))), reverse=True):
            name = str(item.get("name", "")).strip()
            low = name.lower()
            if any(low != str(existing.get("name", "")).strip().lower() and low in str(existing.get("name", "")).strip().lower() for existing in cleaned):
                continue
            cleaned.append(item)

        return cleaned
