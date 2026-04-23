from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class TourismEvidenceScore:
    """
    Señal complementaria de evidencia turística.
    No clasifica por sí misma.
    Sirve para:
    - reforzar entidades con contexto turístico claro,
    - penalizar fragmentos narrativos,
    - dejar trazabilidad.
    """

    def __init__(self):
        self.instance_terms = {
            "ayuntamiento": 3.0,
            "catedral": 3.0,
            "iglesia": 2.5,
            "capilla": 2.5,
            "monasterio": 2.5,
            "convento": 2.5,
            "palacio": 2.5,
            "castillo": 2.5,
            "puente": 2.0,
            "plaza": 2.0,
            "parque": 1.5,
            "mercado": 1.5,
            "museo": 2.5,
            "fronton": 2.0,
            "frontón": 2.0,
            "camino de santiago": 3.0,
            "ruta": 1.5,
            "festival": 2.5,
            "san fermin": 3.0,
            "san fermín": 3.0,
        }

        self.context_terms = {
            "monumento": 1.5,
            "escultura": 1.5,
            "estatua": 1.5,
            "busto": 1.5,
            "homenaje": 1.2,
            "retrato": 1.2,
            "peregrinación": 1.5,
            "peregrinacion": 1.5,
            "ruta": 1.0,
            "patrimonio": 1.0,
            "turismo": 0.8,
            "visita": 0.8,
            "historia": 0.7,
            "cultural": 0.7,
            "festival": 1.0,
            "fiesta": 0.8,
        }

        self.negative_fragments = {
            "ir al contenido",
            "todos los derechos reservados",
            "accesibilidad",
            "reserva tu actividad",
            "ver más",
            "ver mas",
            "mapas",
            "google maps",
            "compartir",
            "newsletter",
            "guías",
            "convention bureau",
            "área profesional",
            "area profesional",
        }

    def _norm(self, text: Any) -> str:
        text = "" if text is None else str(text)
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _name(self, entity: Dict[str, Any]) -> str:
        return self._norm(
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        )

    def _context(self, entity: Dict[str, Any]) -> str:
        parts = [
            entity.get("source_text") or "",
            entity.get("description") or "",
            entity.get("short_description") or "",
            entity.get("long_description") or "",
        ]
        return self._norm(" ".join(str(p) for p in parts if p))

    def score_entity(
        self,
        entity: Dict[str, Any],
        page_url: str = "",
        page_signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        page_signals = page_signals or {}

        name = self._name(entity)
        context = self._context(entity)
        score = 0.0
        reasons: List[str] = []

        if not name:
            return {
                "score": -5.0,
                "decision": "weak",
                "reasons": ["missing_name"],
            }

        for term, value in self.instance_terms.items():
            if term in name:
                score += value
                reasons.append(f"instance:{term}")

        for term, value in self.context_terms.items():
            if term in context:
                score += value
                reasons.append(f"context:{term}")

        if len(name.split()) >= 2:
            score += 0.7
            reasons.append("multiword_name")

        if entity.get("wikidata_id"):
            score += 1.5
            reasons.append("wikidata_link")

        coords = entity.get("coordinates") or {}
        if isinstance(coords, dict) and coords.get("lat") is not None and coords.get("lng") is not None:
            score += 1.2
            reasons.append("has_coordinates")

        if entity.get("image") or entity.get("mainImage"):
            score += 0.8
            reasons.append("has_image")

        all_text = f"{name} {context}"
        for bad in self.negative_fragments:
            if bad in all_text:
                score -= 2.5
                reasons.append(f"negative:{bad}")

        if len(name.split()) >= 6:
            score -= 2.0
            reasons.append("very_long_name")

        decision = "strong" if score >= 4.0 else "medium" if score >= 1.5 else "weak"

        return {
            "score": round(score, 3),
            "decision": decision,
            "reasons": reasons,
        }