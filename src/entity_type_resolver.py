from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


def _norm(text: str) -> str:
    text = text or ""
    text = text.strip().lower()
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    return re.sub(r"\s+", " ", text)


class EntityTypeResolver:
    """Resuelve tipos con evidencia acumulada y opción real de Unknown.

    No escribe una clase fuerte salvo que haya evidencia positiva suficiente.
    """

    def __init__(self) -> None:
        self.person_keywords = {
            "cantaor", "cantaora", "artista", "bailaor", "bailaora", "compositor",
            "poeta", "pintor", "escritor", "nacio", "murio", "fue", "biografia",
        }
        self.event_keywords = {
            "festival", "evento", "bienal", "edicion", "programacion", "programación",
            "concierto", "agenda", "se celebra", "celebra", "entradas",
        }
        self.place_keywords = {
            "altozano", "barrio", "plaza", "calle", "alcazar", "alcázar", "parque",
            "museo", "teatro", "tablao", "isla magica", "isla mágica", "puente",
            "palacio", "iglesia", "capilla", "catedral", "mercado", "ayuntamiento",
        }
        self.organization_keywords = {
            "fundacion", "fundación", "asociacion", "asociación", "academia", "centro",
            "consorcio", "patronato", "empresa",
        }
        self.concept_keywords = {
            "arte", "cante", "baile", "poesia", "poesía", "sentimiento", "tradicion",
            "tradición", "folclore", "folklore", "estilo", "género", "genero",
        }
        self.person_exact = {
            "manolo caracol", "la nina de los peines", "nina de los peines", "pastora pavon",
        }
        self.event_exact = {
            "bienal de flamenco", "bienal de flamenco de sevilla",
        }
        self.place_exact = {
            "sevilla", "triana", "altozano de triana", "real alcazar", "real alcazar de sevilla",
            "isla magica", "isla mágica",
        }
        self.concept_exact = {
            "flamenco", "cante jondo",
        }
        self.operational_fields = {"address", "phone", "coordinates", "schedule", "openingHours", "url"}
        self.forbidden_final_types = {"Thing", "Entity", "Item"}

    def _vote(self, votes: Dict[str, float], label: str, amount: float) -> None:
        votes[label] = votes.get(label, 0.0) + amount

    def _best(self, votes: Dict[str, float]) -> Dict[str, Any]:
        if not votes:
            return {"class": "Unknown", "confidence": 0.0, "evidence": [], "votes": {}}
        ordered = sorted(votes.items(), key=lambda kv: kv[1], reverse=True)
        best_label, best_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0.0
        margin = best_score - second_score
        confidence = min(0.97, round(0.45 + (best_score * 0.08) + (margin * 0.04), 3))
        if best_label in self.forbidden_final_types:
            return {"class": "Unknown", "confidence": min(confidence, 0.51), "evidence": ["forbidden_final_type"], "votes": votes}
        if best_score < 2.5 or margin < 0.5:
            return {"class": "Unknown", "confidence": min(confidence, 0.64), "evidence": [], "votes": votes}
        return {"class": best_label, "confidence": confidence, "evidence": [], "votes": votes}

    def resolve(
        self,
        mention: str,
        context: str = "",
        block_text: str = "",
        page_signals: Optional[Dict[str, Any]] = None,
        properties: Optional[Dict[str, Any]] = None,
        expected_type: Optional[str] = None,
        ontology_candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        mention_n = _norm(mention)
        context_n = _norm(f"{context} {block_text}")
        page_signals = page_signals or {}
        properties = properties or {}
        ontology_candidates = ontology_candidates or []
        evidence: List[str] = []
        votes: Dict[str, float] = {}

        if mention_n in self.person_exact:
            return {"class": "Person", "confidence": 0.95, "evidence": ["person_exact"], "votes": {"Person": 6.0}}
        if mention_n in self.event_exact:
            return {"class": "Event", "confidence": 0.95, "evidence": ["event_exact"], "votes": {"Event": 6.0}}
        if mention_n in self.place_exact:
            return {"class": "Place", "confidence": 0.95, "evidence": ["place_exact"], "votes": {"Place": 6.0}}
        if mention_n in self.concept_exact:
            return {"class": "Concept", "confidence": 0.90, "evidence": ["concept_exact"], "votes": {"Concept": 5.0}}

        if any(k in context_n for k in self.person_keywords) and len(mention.split()) >= 2:
            self._vote(votes, "Person", 2.5)
            evidence.append("person_context")

        if any(k in mention_n for k in self.event_keywords) or any(k in context_n for k in self.event_keywords):
            self._vote(votes, "Event", 2.2)
            evidence.append("event_keywords")

        if any(k in mention_n for k in self.organization_keywords):
            self._vote(votes, "Organization", 2.0)
            evidence.append("organization_keywords")

        if any(k in mention_n for k in self.place_keywords):
            self._vote(votes, "Place", 2.0)
            evidence.append("place_keywords")

        if any(k in mention_n for k in self.concept_keywords):
            self._vote(votes, "Concept", 1.5)
            evidence.append("concept_keywords")

        if expected_type:
            self._vote(votes, str(expected_type).strip(), 0.8)
            evidence.append("expected_type_hint")

        h1 = _norm(page_signals.get("h1") or "")
        title = _norm(page_signals.get("title") or "")
        if mention_n and h1 and (mention_n in h1 or h1 in mention_n):
            self._vote(votes, "Place", 0.8)
            self._vote(votes, "Event", 0.5)
            evidence.append("page_h1_match")
        if mention_n and title and (mention_n in title or title in mention_n):
            self._vote(votes, "Place", 0.5)
            self._vote(votes, "Event", 0.3)
            evidence.append("page_title_match")

        if any(properties.get(k) not in (None, "", [], {}) for k in self.operational_fields):
            self._vote(votes, "Place", 1.2)
            self._vote(votes, "Organization", 0.7)
            votes["Concept"] = votes.get("Concept", 0.0) - 2.5
            evidence.append("operational_properties")

        for cand in ontology_candidates[:2]:
            label = str(cand.get("label") or "").strip()
            score = float(cand.get("score") or 0.0)
            if not label or label in self.forbidden_final_types or score < 0.72:
                continue
            self._vote(votes, label, 1.0 + (score - 0.72) * 3)
            evidence.append(f"ontology:{label}")

        result = self._best(votes)
        result["evidence"] = evidence

        # endurecer Concept: sólo cuando no haya señal operativa o locativa.
        if result["class"] == "Concept":
            if any(properties.get(k) not in (None, "", [], {}) for k in {"address", "phone", "coordinates", "schedule", "openingHours"}):
                result["class"] = "Unknown"
                result["confidence"] = min(result.get("confidence", 0.0), 0.55)
                result["evidence"].append("concept_demoted_by_operational_props")

        return result
