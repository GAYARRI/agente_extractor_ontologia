from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class EntityRanker:
    """
    Rankea entidades candidatas priorizando:
    - nombres turísticos reales
    - nombres completos y naturales
    - entidades alineadas con el contenido de la página

    Compatible con entidades tipo dict.
    """

    def __init__(self, type_normalizer=None, ontology_distance=None):
        self.type_normalizer = type_normalizer
        self.ontology_distance = ontology_distance

        # Debug desactivado por defecto
        self.debug = False

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
        }

        self.bad_words = {
            "cada",
            "día",
            "dia",
            "semana",
            "historia",
            "información",
            "informacion",
            "curiosidades",
            "evento",
            "celebra",
            "descubre",
            "conoce",
            "planes",
            "agenda",
            "turismo",
            "cultura",
            "analytics",
            "google",
            "patrimonio",
            "cultural",
            "inmaterial",
        }

        self.bad_verbs = {
            "es",
            "son",
            "fue",
            "eran",
            "donde",
            "cuando",
            "como",
            "aunque",
            "existe",
            "existía",
            "existia",
            "celebra",
        }

        self.invalid_trailing_words = {
            "de",
            "del",
            "la",
            "las",
            "el",
            "los",
            "e",
            "y",
            "a",
            "al",
        }

        self.generic_entities = {
            "sevilla",
            "flamenco",
            "cultura",
            "turismo",
            "curiosidades",
            "el flamenco",
            "la sevilla",
            "patrimonio cultural inmaterial",
            "google analytics",
        }

    # =========================================================
    # Helpers
    # =========================================================

    def _entity_name(self, entity: Dict[str, Any]) -> str:
        return (
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        ).strip()

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except Exception:
            return default

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü]+", (text or "").lower())

    def _has_anchor_word(self, text: str) -> bool:
        tokens = self._tokenize(text)
        return any(t in self.anchor_words for t in tokens)

    def _looks_truncated(self, text: str) -> bool:
        tokens = self._tokenize(text)
        if not tokens:
            return True

        if tokens[-1] in self.invalid_trailing_words:
            return True

        if len(tokens) >= 2 and tokens[-1] in self.bad_verbs:
            return True

        return False

    def _name_quality_score(self, name: str) -> float:
        if not name:
            return -10.0

        score = 0.0
        tokens = self._tokenize(name)
        token_count = len(tokens)
        low = name.lower().strip()

        # positivos
        if self._has_anchor_word(name):
            score += 2.5

        if 2 <= token_count <= 5:
            score += 1.5
        elif token_count == 1:
            score -= 1.0
        elif token_count > 7:
            score -= 2.0

        if " de " in low or " del " in low:
            score += 0.8

        if all(word[:1].isupper() for word in name.split() if word[:1].isalpha()):
            score += 0.5

        # negativos generales
        if any(t in self.bad_words for t in tokens):
            score -= 2.0

        if any(t in self.bad_verbs for t in tokens):
            score -= 2.5

        if low in self.generic_entities:
            score -= 2.0

        if self._looks_truncated(name):
            score -= 2.5

        # penalizaciones específicas
        if low in {"google analytics", "la sevilla", "el flamenco", "patrimonio cultural inmaterial"}:
            score -= 4.0

        if "google" in tokens or "analytics" in tokens:
            score -= 4.0

        if "patrimonio" in tokens and "cultural" in tokens:
            score -= 3.0

        if tokens and tokens[0] in {"el", "la", "los", "las"} and not self._has_anchor_word(name):
            score -= 2.5

        if token_count == 2 and tokens[0] == "sevilla" and tokens[1] not in self.anchor_words:
            score -= 3.0

        if token_count == 2 and tokens[0] in {"el", "la", "los", "las"} and not self._has_anchor_word(name):
            score -= 1.5

        return score

    def _page_relevance_score(self, name: str, page_text: Optional[str]) -> float:
        if not name or not page_text:
            return 0.0

        name_low = name.lower()
        page_low = page_text.lower()

        score = 0.0

        if name_low in page_low:
            score += 1.0

        name_tokens = [t for t in self._tokenize(name) if len(t) > 2]
        if name_tokens:
            hits = sum(1 for t in name_tokens if t in page_low)
            score += min(hits * 0.25, 1.0)

        return score

    def _semantic_score(self, entity: Dict[str, Any]) -> float:
        for key in ("semantic_score", "semantic_similarity", "score"):
            value = entity.get(key)
            if value is not None:
                return self._safe_float(value, 0.0)
        return 0.0

    def _type_score(self, entity: Dict[str, Any], target_type: Optional[str]) -> float:
        if not target_type or self.type_normalizer is None or self.ontology_distance is None:
            return 0.0

        raw_type = (
            entity.get("semantic_type")
            or entity.get("class")
            or entity.get("type")
            or "Thing"
        )

        normalized_type = self.type_normalizer.normalize_with_context(
            raw_type=raw_type,
            entity_name=self._entity_name(entity),
            page_text="",
            default="Thing",
        )

        entity["normalized_type"] = normalized_type

        try:
            similarity = self.ontology_distance.similarity(normalized_type, target_type)
            distance = self.ontology_distance.distance(normalized_type, target_type)
        except Exception:
            similarity = 0.0
            distance = 99

        entity["class_similarity"] = similarity
        entity["class_distance"] = distance

        score = similarity * 2.0

        if distance == 0:
            score += 1.0
        elif distance == 1:
            score += 0.4
        elif distance >= 3:
            score -= 0.5

        return score

    # =========================================================
    # API
    # =========================================================

    def rank(
        self,
        candidates: List[Dict[str, Any]],
        target_type: Optional[str] = None,
        page_text: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        ranked: List[Dict[str, Any]] = []

        for entity in candidates:
            if not isinstance(entity, dict):
                if self.debug:
                    print(f"[RANKER] skipping non-dict entity: {entity!r}")
                continue

            item = dict(entity)
            name = self._entity_name(item)

            if not name:
                if self.debug:
                    print(f"[RANKER] skipping empty-name entity: {item!r}")
                continue

            semantic = self._semantic_score(item)
            name_quality = self._name_quality_score(name)
            page_relevance = self._page_relevance_score(name, page_text)
            type_score = self._type_score(item, target_type)

            final_score = (
                semantic * 1.2
                + name_quality
                + page_relevance
                + type_score
            )

            item["name_quality_score"] = round(name_quality, 4)
            item["page_relevance_score"] = round(page_relevance, 4)
            item["semantic_similarity"] = round(semantic, 4)
            item["final_score"] = round(final_score, 4)

            # compatibilidad con el resto del pipeline
            item["score"] = item["final_score"]

            if self.debug:
                print(
                    "[RANKER] entity=",
                    name,
                    "| semantic=",
                    semantic,
                    "| name_quality=",
                    name_quality,
                    "| page_relevance=",
                    page_relevance,
                    "| type_score=",
                    type_score,
                    "| final_score=",
                    final_score,
                )

            ranked.append(item)

        ranked.sort(
            key=lambda x: (
                x.get("final_score", 0.0),
                x.get("name_quality_score", 0.0),
                x.get("page_relevance_score", 0.0),
                x.get("semantic_similarity", 0.0),
            ),
            reverse=True,
        )

        return ranked