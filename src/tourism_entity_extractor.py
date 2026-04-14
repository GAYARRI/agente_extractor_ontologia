from __future__ import annotations

import re
from typing import Any, Dict, List


class TourismEntityExtractor:
    """
    Extractor más restrictivo para reducir ruido editorial.

    Soporta bloques:
    - string
    - dict
    - list
    - tuple
    """

    def __init__(self):
        self.patterns = [
            r"\b(?:Museo|Iglesia|Capilla|Catedral|Basílica|Basilica|Castillo|Alcázar|Alcazar|Plaza|Ayuntamiento|Estadio|Hotel|Restaurante|Monasterio|Convento|Palacio|Torre|Puente|Parque|Jardín|Jardin|Barrio|Mercado|Centro)\b(?:\s+(?:de|del|la|las|el|los|y|e|[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+)){0,8}",
            r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñü]+){1,5}\b",
        ]

        self.bad_exact = {
            "día mundial",
            "dia mundial",
            "el día mundial",
            "el dia mundial",
            "semana santa",
            "qué hacer",
            "que hacer",
            "sevilla sevilla",
            "sevilla academias",
            "sevilla cada",
            "la sevilla",
            "en sevilla",
            "día internacional",
            "dia internacional",
            "más información",
            "mas informacion",
            "declarado patrimonio cultural inmaterial",
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
            "sevilla",
            "flamenco",
            "curiosidades",
            "declarado",
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
            "en ",
            "declarado ",
            "declarada ",
        )

        self.bad_contains = (
            "academias",
            "curiosidades",
            "información",
            "informacion",
            "qué hacer",
            "que hacer",
            "google analytics",
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
            "flamenco",
            "bienal",
            "alcázar",
        }

        self.trailing_cut_tokens = {
            "es", "son", "fue", "fueron", "era", "eran",
            "que", "donde", "cuando", "como", "aunque",
            "uno", "una", "unos", "unas",
            "este", "esta", "estos", "estas",
            "su", "sus", "un", "una",
            "al", "a",
            "e", "y",
            "leer",
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
        }

    # =========================================================
    # Helpers
    # =========================================================

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
                    parts.extend(
                        str(x).strip()
                        for x in value
                        if x is not None and str(x).strip()
                    )

            return " ".join(parts).strip()

        if isinstance(block, (list, tuple)):
            return " ".join(
                str(x).strip()
                for x in block
                if x is not None and str(x).strip()
            ).strip()

        return str(block).strip()

    def _normalize_entity(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text.strip(" ,.;:-|")

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

    def _looks_like_bad_place_phrase(self, words: List[str]) -> bool:
        if len(words) != 2:
            return False

        first, second = words[0], words[1]

        if first == "sevilla" and second not in self.anchor_words:
            return True

        if first in {"en", "la", "el"} and second == "sevilla":
            return True

        return False

    def _is_valid_candidate(self, text: str) -> bool:
        if not text:
            return False

        text = text.strip()
        low = text.lower()
        words = low.split()

        if len(text) < 4:
            return False

        if len(words) > 7:
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

        if low.endswith((" es", " son", " fue", " era", " que", " donde", " como")):
            return False

        if words and words[-1] in self.trailing_invalid_endings:
            return False

        if self._has_anchor_word(low) and len(words) == 1:
            return False

        if self._has_anchor_word(low) and len(words) == 2 and words[-1] in {"de", "del", "la", "el"}:
            return False

        if words and words[0] in self.bad_first_words and not self._has_anchor_word(low):
            return False

        if self._looks_like_bad_place_phrase(words):
            return False

        if len(words) == 2 and not self._has_anchor_word(low):
            generic_two_word = {
                "real alcázar",
                "real alcazar",
            }
            if low not in generic_two_word:
                raw_words = text.split()
                if not all(w[:1].isupper() for w in raw_words):
                    return False

        return True

    # =========================================================
    # API
    # =========================================================

    def extract(self, blocks: List[Any]) -> List[Dict[str, Any]]:
        entities: List[Dict[str, Any]] = []
        seen = set()

        for block in blocks or []:
            text = self._block_to_text(block)

            if not text:
                continue

            for pattern in self.patterns:
                matches = re.findall(pattern, text)

                for match in matches:
                    entity_text = self._normalize_entity(match)
                    entity_text = self._trim_trailing_noise(entity_text)

                    if not self._is_valid_candidate(entity_text):
                        continue

                    key = entity_text.lower()
                    if key in seen:
                        continue

                    seen.add(key)

                    entities.append(
                        {
                            "entity": entity_text,
                            "entity_name": entity_text,
                            "label": entity_text,
                            "name": entity_text,
                            "class": "Thing",
                            "type": "Thing",
                            "score": 0.5,
                            "source_text": text[:500],
                        }
                    )

        return entities