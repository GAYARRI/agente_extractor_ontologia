from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


class OntologyMatcher:
    def __init__(self, ontology_index):
        self.index = ontology_index
        self.model = ontology_index.model
        self.top_k = 8
        self.min_score = 0.72
        self.high_confidence = 0.82
        self.generic_blocklist = {"Thing", "Entity", "Item", "Concept"}

    def _is_valid_class(self, uri: str, label: str = "") -> bool:
        hierarchy = self.index.get_hierarchy(uri)
        if not hierarchy:
            return False
        if str(label or "").strip() in self.generic_blocklist:
            return False
        return True

    def _score_adjustment(
        self,
        label: str,
        context: str = "",
        expected_type: Optional[str] = None,
        evidence_score: float = 0.0,
    ) -> float:
        label_l = str(label or "").lower()
        context_l = str(context or "").lower()
        adj = 0.0
        if expected_type and str(expected_type).lower() == label_l.lower():
            adj += 0.03
        if label_l == "event" and any(x in context_l for x in ["festival", "agenda", "programación", "programacion", "edición", "edicion"]):
            adj += 0.03
        if label_l in {"place", "museum", "monument", "church", "cathedral", "basilica", "square"} and any(
            x in context_l for x in ["dirección", "direccion", "ubicado", "situado", "visita", "horario", "horarios"]
        ):
            adj += 0.03
        adj += min(0.04, max(0.0, evidence_score) * 0.005)
        return adj

    def match(
        self,
        entity: str,
        context: str = "",
        expected_type: Optional[str] = None,
        evidence_score: float = 0.0,
        allowed_classes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        vec = self.model.encode([entity])
        scores = cosine_similarity(vec, self.index.embeddings)[0]
        top_indices = np.argsort(scores)[-self.top_k:][::-1]
        results: List[Dict[str, Any]] = []
        allowed = {str(x).strip() for x in (allowed_classes or []) if str(x).strip()}
        for idx in top_indices:
            uri = self.index.uris[idx]
            label = self.index.labels[idx]
            if len(label) < 4:
                continue
            if allowed and label not in allowed:
                continue
            base_score = float(scores[idx])
            final_score = round(base_score + self._score_adjustment(label, context=context, expected_type=expected_type, evidence_score=evidence_score), 4)
            if final_score < self.min_score:
                continue
            if not self._is_valid_class(uri, label=label):
                continue
            results.append({"label": label, "uri": uri, "score": final_score, "base_score": base_score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def best_match(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        matches = self.match(*args, **kwargs)
        return matches[0] if matches else None
