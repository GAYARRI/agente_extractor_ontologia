from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer


class SemanticSimilarityMatcher:
    """
    Enriquecedor semántico para entidades ya extraídas.

    Importante:
    - no sustituye la entidad
    - añade semantic_type y semantic_score
    - filtra tipos con score demasiado bajo
    - intenta evitar asignaciones absurdas tipo Spa / EquestrianClub
    """

    def __init__(self, ontology_index):
        self.ontology_index = ontology_index

        self.model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        self.classes = list(self.ontology_index.classes.keys())

        # Más conservador que antes
        self.min_similarity = 0.52

        # Tipos que suelen salir como falsos positivos en este dominio
        self.soft_blocked_type_fragments = {
            "Spa",
            "EquestrianClub",
            "TaxiStand",
            "Spring",
            "MiscellaneousService",
            "DayOfTheWeek",
        }

        # Señales de nombre que sí apoyan ciertos tipos
        self.name_type_hints = {
            "Cathedral": {"catedral"},
            "Church": {"iglesia"},
            "Basilica": {"basílica", "basilica"},
            "Chapel": {"capilla"},
            "Alcazar": {"alcázar", "alcazar"},
            "Castle": {"castillo"},
            "Square": {"plaza"},
            "Museum": {"museo"},
            "Monastery": {"monasterio", "convento"},
            "TownHall": {"ayuntamiento"},
            "Stadium": {"estadio"},
            "Park": {"parque", "jardín", "jardin"},
            "Market": {"mercado"},
            "Neighborhood": {"barrio"},
            "Bridge": {"puente"},
            "Tower": {"torre"},
            "Hotel": {"hotel"},
            "Restaurant": {"restaurante"},
        }

        if not self.classes:
            print("⚠ No se encontraron clases ontológicas")
            self.class_embeddings = []
            return

        self.class_embeddings = self.model.encode(self.classes)

    # ---------------------------------------------------
    # similitud coseno
    # ---------------------------------------------------

    def cosine(self, a, b) -> float:
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def _entity_name(self, entity: Dict[str, Any]) -> str:
        return (
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        ).strip()

    def _normalize_text(self, text: str) -> str:
        return " ".join((text or "").lower().split())

    def _supports_type_by_name(self, entity_name: str, ontology_class: str) -> bool:
        low_name = self._normalize_text(entity_name)

        for class_fragment, hints in self.name_type_hints.items():
            if class_fragment in ontology_class:
                return any(hint in low_name for hint in hints)

        return False

    def _is_soft_blocked_type(self, ontology_class: str) -> bool:
        return any(fragment in ontology_class for fragment in self.soft_blocked_type_fragments)

    def _adjust_score_with_name_hints(self, entity_name: str, ontology_class: str, base_score: float) -> float:
        score = base_score

        # boost si el nombre y el tipo cuadran claramente
        if self._supports_type_by_name(entity_name, ontology_class):
            score += 0.10

        # penalización si es un tipo históricamente absurdo para este dominio
        if self._is_soft_blocked_type(ontology_class):
            score -= 0.12

        return score

    # ---------------------------------------------------
    # matching semántico
    # ---------------------------------------------------

    def match(self, entities, page_text=None):
        if not self.classes:
            return []

        results: List[Dict[str, Any]] = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            name = self._entity_name(entity)

            if not name:
                continue

            try:
                emb = self.model.encode([name])[0]
            except Exception as e:
                print("Error generando embedding:", e)
                continue

            best_score = -1.0
            best_class = None

            for i, ontology_class in enumerate(self.classes):
                raw_score = self.cosine(emb, self.class_embeddings[i])
                score = self._adjust_score_with_name_hints(name, ontology_class, raw_score)

                if score > best_score:
                    best_score = score
                    best_class = ontology_class

            enriched = dict(entity)

            # asignar solo si supera umbral conservador
            if best_class is not None and best_score >= self.min_similarity:
                enriched["semantic_type"] = best_class
                enriched["semantic_score"] = round(float(best_score), 4)
            else:
                enriched["semantic_type"] = ""
                enriched["semantic_score"] = 0.0

            # no tocar score base aquí
            results.append(enriched)

        return results