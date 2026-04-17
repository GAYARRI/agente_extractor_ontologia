import re
from typing import List, Set

try:
    from src.entity_filter import is_valid_entity, normalize_entity_text
except Exception:
    def normalize_entity_text(text: str) -> str:
        text = str(text or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def is_valid_entity(entity: str, context: str = "") -> bool:
        entity = str(entity or "").strip()
        if not entity or len(entity) < 3:
            return False
        return True

try:
    import spacy  # type: ignore
    SPACY_AVAILABLE = True
except Exception:
    spacy = None
    SPACY_AVAILABLE = False


class TourismEntityExtractor:
    def __init__(self, model_name: str = "es_core_news_md", use_spacy: bool = True):
        self.model_name = model_name
        self.use_spacy = bool(use_spacy and SPACY_AVAILABLE)
        self.nlp = None

        if self.use_spacy:
            try:
                self.nlp = spacy.load(self.model_name)
            except Exception:
                self.use_spacy = False
                self.nlp = None

        self.bad_words = {
            "pamplona",
            "iruña",
            "navarra",
            "turismo",
            "gastronomía",
            "gastronomia",
            "historia",
            "viaje",
            "descubre",
            "visitantes",
        }

        self.bad_patterns = [
            r"utilizamos cookies",
            r"más info",
            r"mas info",
            r"leer más",
            r"leer mas",
            r"todo lo que necesitas",
            r"^\d+_",
        ]

        self.category_heading_patterns = [
            r"^sidrer[ií]as en ",
            r"^restaurantes en ",
            r"^bares en ",
            r"^hoteles en ",
            r"^museos en ",
            r"^cafeter[ií]as en ",
            r"^alojamientos en ",
        ]

    def clean_text(self, text) -> str:
        if isinstance(text, list):
            parts = []
            for item in text:
                if isinstance(item, dict):
                    value = item.get("text") or item.get("content") or item.get("html") or ""
                    if value:
                        parts.append(str(value))
                elif item is not None:
                    parts.append(str(item))
            text = " ".join(parts)
        elif text is None:
            text = ""
        else:
            text = str(text)

        text = re.sub(r"\s+", " ", text)

        for pattern in self.bad_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        text = re.sub(r"\b\d+_\s*", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _looks_like_category_heading(self, entity: str) -> bool:
        norm = normalize_entity_text(entity).lower()
        return any(re.match(pattern, norm) for pattern in self.category_heading_patterns)

    def _looks_like_bad_compound(self, entity: str) -> bool:
        norm = normalize_entity_text(entity)
        if not norm:
            return True

        lower = norm.lower()

        if self._looks_like_category_heading(norm):
            return True

        suspicious_fragments = [
            "gastronomía turismo",
            "gastronomia turismo",
            "turismo salud",
            "salud turismo",
            "santiago gastronomía turismo",
            "santiago gastronomia turismo",
        ]
        if any(fragment in lower for fragment in suspicious_fragments):
            return True

        words = norm.split()
        if len(words) >= 5 and all(w[:1].isupper() for w in words if w):
            return True

        return False

    def _rule_based_candidates(self, text: str) -> Set[str]:
        candidates: Set[str] = set()

        patterns = [
            r"\bSan\s+Ferm[ií]n(?:\s+Pamplona)?\b",
            r"\bCatedral\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+\b",
            r"\bAyuntamiento\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]+\b",
            r"\bPlaza\s+Consistorial\b",
            r"\bCamino\s+Franc[eé]s\b",
            r"\bCamino\s+Primitivo\b",
            r"\bCamino\s+Baztan[eé]s\b",
            r"\bCamino\s+de\s+Santiago\b",
            r"\bSidrer[ií]as\s+En\s+Pamplona\b",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                entity = normalize_entity_text(match.group(0))
                if entity:
                    candidates.add(entity)

        return candidates

    def _spacy_candidates(self, text: str) -> Set[str]:
        if not self.use_spacy or self.nlp is None:
            return set()

        entities: Set[str] = set()

        try:
            doc = self.nlp(text)
        except Exception:
            return set()

        for ent in doc.ents:
            entity = normalize_entity_text(ent.text)
            if not entity:
                continue
            if entity.lower() in self.bad_words:
                continue
            entities.add(entity)

        return entities

    def _postfilter_entities(self, entities: Set[str], context: str) -> List[str]:
        final_entities: List[str] = []

        sorted_entities = sorted(entities, key=lambda x: (-len(x), x.lower()))

        for entity in sorted_entities:
            entity_l = entity.lower()

            if not entity.strip():
                continue

            if entity_l in self.bad_words:
                continue

            if self._looks_like_category_heading(entity):
                continue

            if self._looks_like_bad_compound(entity):
                continue

            if not is_valid_entity(entity, context=context):
                continue

            if any(
                entity_l != other.lower() and entity_l in other.lower()
                for other in final_entities
            ):
                continue

            final_entities.append(entity)

        return final_entities

    def extract(self, text) -> List[str]:
        text = self.clean_text(text)
        if not text or not isinstance(text, str):
            return []

        entities: Set[str] = set()

        entities.update(self._spacy_candidates(text))
        entities.update(self._rule_based_candidates(text))

        return self._postfilter_entities(entities, context=text)