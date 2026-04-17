from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional


class EntityTypeResolver:
    """
    Conservative resolver:
    - prefers precision over recall
    - rejects weak semantic matches
    - uses lexical hints before ontology drift
    """

    def __init__(self):
        self.weak_types = {"", "thing", "unknown", "entity", "item"}
        self.forbidden_final_types = {"Thing", "Entity", "Item", "Location"}

        self.min_semantic_confidence = 0.70
        self.strong_semantic_confidence = 0.80

        self.lexical_rules = [
            (r"\bayuntamiento\b|\btown hall\b", "TownHall"),
            (r"\bplaza\b|\bsquare\b", "Square"),
            (r"\bcatedral\b|\bcathedral\b", "Cathedral"),
            (r"\bbasilica\b|\bbasílica\b", "Basilica"),
            (r"\biglesia\b|\bchurch\b", "Church"),
            (r"\bcapilla\b|\bchapel\b", "Chapel"),
            (r"\bmonasterio\b|\bmonastery\b", "Monastery"),
            (r"\bmuseo\b|\bmuseum\b", "Museum"),
            (r"\bcastillo\b|\bcastle\b", "Castle"),
            (r"\balc[aá]zar\b", "Alcazar"),
            (r"\bmonumento\b|\bmonument\b|\bestatua\b|\bescultura\b", "Monument"),
            (r"\bparque\b|\bpark\b", "Park"),
            (r"\bjardines\b|\bgarden\b", "Garden"),
            (r"\bpuente\b|\bbridge\b", "Bridge"),
            (r"\bmercado\b|\bmarket\b", "Market"),
            (r"\bteatro\b|\btheatre\b|\btheater\b", "Theatre"),
            (r"\barena\b", "Arena"),
            (r"\bfront[oó]n\b", "SportsVenue"),
            (r"\bportal\b", "Gate"),
            (r"\bmuralla\b|\bmurallas\b|\bfortification\b", "Fortification"),
            (r"\bevento\b|\bevent\b|\bfestival\b|\bconcierto\b", "Event"),
            (r"\bexcursi[oó]n\b|\bexcursion\b", "Excursion"),
            (r"\bruta\b|\broute\b", "Route"),
            (r"\bvisita guiada\b|\bguided tour\b", "GuidedTour"),
            (r"\bactividad\b|\bactivity\b|\bcicloturismo\b|\bsenderismo\b", "Activity"),
            (r"\brestaurante\b|\brestaurant\b|\bbar\b|\bcaf[eé]\b|\bcafeter[ií]a\b", "FoodEstablishment"),
            (r"\bpostre\b", "Dessert"),
            (r"\blicor\b|\bsidra\b|\bdrink\b", "Drink"),
            (r"\bqueso\b|\bfood product\b", "FoodProduct"),
            (r"\bgoxua\b|\bcuajada\b|\bpantxineta\b|\bajoarriero\b|\bfritos\b|\bpochas\b|\bmenestra\b", "Dish"),
        ]

        self.family_compatibility = {
            "place": {
                "TownHall", "Square", "Cathedral", "Basilica", "Church", "Chapel",
                "Monastery", "Museum", "Castle", "Alcazar", "Monument", "Park",
                "Garden", "Bridge", "Market", "Theatre", "Arena", "SportsVenue",
                "Gate", "Fortification",
            },
            "event": {"Event", "GuidedTour", "Excursion", "Activity"},
            "food": {"FoodEstablishment", "Dish", "Dessert", "Drink", "FoodProduct"},
            "route": {"Route", "GuidedTour", "Excursion", "Activity"},
            "service": {"TourismService", "Organization"},
            "concept": {"Unknown"},
            "unknown": set(),
        }

    def _normalize_text(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    def _normalize_type(self, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        short = raw.split("#")[-1].split("/")[-1].strip()
        return short

    def _is_weak_type(self, value: Any) -> bool:
        t = self._normalize_type(value).lower()
        return t in self.weak_types

    def _is_forbidden_type(self, value: Any) -> bool:
        t = self._normalize_type(value)
        return t in self.forbidden_final_types

    def _vote(self, votes: Dict[str, float], label: str, weight: float) -> None:
        if not label:
            return
        if self._is_forbidden_type(label):
            return
        if self._is_weak_type(label):
            return
        votes[label] += weight

    def _detect_family(self, mention: str, context: str) -> str:
        text = self._normalize_text(f"{mention} {context}")

        if re.search(r"\brestaurante\b|\brestaurant\b|\bpostre\b|\blicor\b|\bsidra\b|\bqueso\b|\bgoxua\b|\bcuajada\b|\bpantxineta\b|\bajoarriero\b|\bfritos\b|\bpochas\b|\bmenestra\b", text):
            return "food"

        if re.search(r"\bevento\b|\bevent\b|\bfestival\b|\bconcierto\b|\bvisita guiada\b|\bguided tour\b|\bexcursi[oó]n\b|\bexcursion\b", text):
            return "event"

        if re.search(r"\bruta\b|\broute\b|\bcicloturismo\b|\bsenderismo\b|\bcamino\b", text):
            return "route"

        if re.search(r"\bbureau\b|\bincoming\b|\bgu[ií]a\b|\bservice\b|\bservicio\b|\bprofesional\b", text):
            return "service"

        if re.search(r"\bayuntamiento\b|\bplaza\b|\bcatedral\b|\biglesia\b|\bcapilla\b|\bmuseo\b|\bcastillo\b|\bparque\b|\bjardines\b|\bpuente\b|\bteatro\b|\barena\b|\bfront[oó]n\b|\bportal\b|\bmurallas?\b|\bmercado\b", text):
            return "place"

        if re.search(r"\bpelota vasca\b|\bedad media\b|\bgastronom[ií]a\b|\bcultura\b", text):
            return "concept"

        return "unknown"

    def _lexical_candidates(self, mention: str, context: str) -> List[str]:
        text = self._normalize_text(f"{mention} {context}")
        out: List[str] = []
        for pattern, label in self.lexical_rules:
            if re.search(pattern, text, flags=re.IGNORECASE) and label not in out:
                out.append(label)
        return out

    def _compatible_with_family(self, label: str, family: str) -> bool:
        if family == "unknown":
            return True
        allowed = self.family_compatibility.get(family, set())
        if not allowed:
            return True
        return label in allowed

    def _best(self, votes: Dict[str, float]) -> Dict[str, Any]:
        if not votes:
            return {"class": "Unknown", "score": 0.0, "margin": 0.0}

        ordered = sorted(votes.items(), key=lambda x: (-x[1], x[0].lower()))
        best_label, best_score = ordered[0]
        second_score = ordered[1][1] if len(ordered) > 1 else 0.0
        margin = best_score - second_score

        if best_score < 3.0 or margin < 0.7:
            return {"class": "Unknown", "score": best_score, "margin": margin}

        return {"class": best_label, "score": best_score, "margin": margin}

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
        page_signals = page_signals or {}
        properties = properties or {}
        ontology_candidates = ontology_candidates or []

        mention = str(mention or "").strip()
        context = str(context or "").strip()
        block_text = str(block_text or "").strip()

        evidence: List[str] = []
        votes: Dict[str, float] = defaultdict(float)

        family = self._detect_family(mention, f"{context} {block_text}")

        # 1) strong lexical evidence first
        lexical = self._lexical_candidates(mention, f"{context} {block_text}")
        for label in lexical:
            self._vote(votes, label, 3.5)
            evidence.append(f"lexical:{label}")

        # 2) expected_type can bias lightly
        normalized_expected = self._normalize_type(expected_type)
        if normalized_expected and not self._is_forbidden_type(normalized_expected) and not self._is_weak_type(normalized_expected):
            if self._compatible_with_family(normalized_expected, family):
                self._vote(votes, normalized_expected, 1.2)
                evidence.append(f"expected:{normalized_expected}")

        # 3) explicit types already present in properties
        for key in ("class", "type", "normalized_type"):
            candidate = self._normalize_type(properties.get(key))
            if candidate and not self._is_forbidden_type(candidate) and not self._is_weak_type(candidate):
                if self._compatible_with_family(candidate, family):
                    self._vote(votes, candidate, 1.5)
                    evidence.append(f"property:{candidate}")

        # 4) ontology / semantic candidates
        best_semantic_uri = ""
        best_semantic_score = 0.0
        best_semantic_label = ""

        for cand in ontology_candidates[:5]:
            label = self._normalize_type(cand.get("label") or cand.get("class") or cand.get("type"))
            uri = str(cand.get("uri") or cand.get("id") or "").strip()
            score = float(cand.get("score") or 0.0)

            if not label or self._is_forbidden_type(label) or self._is_weak_type(label):
                continue

            if not self._compatible_with_family(label, family):
                continue

            if score >= self.strong_semantic_confidence:
                self._vote(votes, label, 2.5 + (score - self.strong_semantic_confidence) * 4)
                evidence.append(f"semantic_strong:{label}:{score:.4f}")
            elif score >= self.min_semantic_confidence:
                if label in lexical:
                    self._vote(votes, label, 1.8 + (score - self.min_semantic_confidence) * 3)
                    evidence.append(f"semantic_supported:{label}:{score:.4f}")
            else:
                continue

            if score > best_semantic_score:
                best_semantic_score = score
                best_semantic_label = label
                best_semantic_uri = uri

        # 5) final decision
        best = self._best(votes)
        final_class = best["class"]

        if final_class == "Unknown":
            best_semantic_label = ""
            best_semantic_uri = ""
            best_semantic_score = 0.0
        elif final_class != best_semantic_label:
            # if lexical won over semantic, keep class but clear semantic URI unless it matches
            best_semantic_uri = best_semantic_uri if final_class == best_semantic_label else ""
            best_semantic_score = best_semantic_score if final_class == best_semantic_label else 0.0

        return {
            "class": final_class,
            "type": final_class,
            "semantic_type": best_semantic_uri,
            "semantic_score": round(best_semantic_score, 4),
            "family": family,
            "score": round(best.get("score", 0.0), 4),
            "margin": round(best.get("margin", 0.0), 4),
            "evidence": evidence,
            "ontology_candidates_seen": len(ontology_candidates),
        }
