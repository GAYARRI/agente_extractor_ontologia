import re
import spacy

from src.entity_filter import (
    is_valid_entity,
    normalize_entity_text,
)


class TourismEntityExtractor:
    def __init__(self):
        self.nlp = spacy.load("es_core_news_md")

        self.bad_words = {
            "aquí", "ideal", "perfecta", "perfectas", "desde", "practica",
            "navega", "zarpa", "utilizamos", "disfruta", "más", "todo",
            "nuestro", "nuestra", "este", "esta", "estos", "estas",
            "familia", "leer", "descubre", "sevillanos", "visitantes",
        }

        self.bad_patterns = [
            r"utilizamos cookies",
            r"más info",
            r"mas info",
            r"leer más",
            r"leer mas",
            r"todo lo que necesitas",
            r"te queda mucho por descubrir:?",
            r"^\d+_",
        ]

    def clean_text(self, text: str) -> str:
        text = text or ""
        text = re.sub(r"\s+", " ", text)

        for p in self.bad_patterns:
            text = re.sub(p, "", text, flags=re.IGNORECASE)

        # limpia numeraciones tipo 01_ / 02_
        text = re.sub(r"\b\d+_\s*", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _rule_based_candidates(self, text: str):
        candidates = set()

        person_patterns = [
            r"\bManolo Caracol\b",
            r"\bLa Niña de los Peines\b",
            r"\bNiña de los Peines\b",
            r"\bPastora Pav[oó]n\b",
        ]

        place_patterns = [
            r"\bAltozano de Triana\b",
            r"\bReal Alc[aá]zar\b",
            r"\bIsla M[aá]gica\b",
            r"\bSevilla\b",
            r"\bTriana\b",
        ]

        concept_patterns = [
            r"\bcante jondo\b",
        ]

        for pattern in person_patterns + place_patterns + concept_patterns:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                candidates.add(normalize_entity_text(m.group(0)))

        return candidates

    def extract(self, text: str):
        text = self.clean_text(text)
        if not text:
            return []

        doc = self.nlp(text)
        entities = set()

        # spaCy NER
        for ent in doc.ents:
            entity = normalize_entity_text(ent.text)
            if not entity:
                continue
            if entity.lower() in self.bad_words:
                continue
            if is_valid_entity(entity, context=text):
                entities.add(entity)

        # reglas adicionales para nombres históricos y lugares concretos
        for entity in self._rule_based_candidates(text):
            if is_valid_entity(entity, context=text):
                entities.add(entity)

        # evita subtrozos si existe una mención más completa
        final_entities = []
        sorted_entities = sorted(entities, key=lambda x: (-len(x), x.lower()))

        for entity in sorted_entities:
            entity_l = entity.lower()
            if any(
                entity_l != other.lower() and entity_l in other.lower()
                for other in final_entities
            ):
                continue
            final_entities.append(entity)

        return final_entities