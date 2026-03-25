# src/entity_evidence_builder.py

import re
from urllib.parse import urlparse


class EntityEvidenceBuilder:
    def __init__(self):
        self.stop_tokens = {
            "de", "del", "la", "las", "el", "los", "y", "en", "a", "al",
            "por", "para", "con", "sin"
        }

        self.strong_types = {
            "Event",
            "TouristAttraction",
            "Organization",
            "LocalBusiness",
            "Route",
            "Accommodation",
            "TransportInfrastructure",
            "CulturalHeritage",
        }

    # =========================================================
    # Helpers
    # =========================================================

    def _normalize(self, text: str) -> str:
        text = (text or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    def _tokens(self, text: str):
        return [t for t in re.split(r"[^\wáéíóúñü]+", self._normalize(text)) if t]

    def _slug_tokens(self, url: str):
        try:
            path = urlparse(url).path.lower()
        except Exception:
            return []

        return [t for t in re.split(r"[^\w]+", path) if t]

    def _as_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _clean_text(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text

    # =========================================================
    # Evidence components
    # =========================================================

    def _name_evidence(self, label: str):
        score = 0
        flags = []

        tokens = self._tokens(label)
        meaningful = [t for t in tokens if t not in self.stop_tokens]

        if not tokens:
            return 0, ["empty_name"]

        if 2 <= len(tokens) <= 6:
            score += 3
        elif len(tokens) == 1:
            score += 0
            flags.append("single_token_name")
        elif len(tokens) > 8:
            score -= 1
            flags.append("too_long_name")

        if len(meaningful) >= 2:
            score += 2
        elif len(meaningful) == 1:
            score += 0
            flags.append("low_semantic_density")

        # señales de truncado/editorial genéricas
        low = self._normalize(label)
        if low.endswith(" leer"):
            score -= 3
            flags.append("editorial_suffix")
        if low in {"ruta", "evento", "mercado", "servicios"}:
            score -= 3
            flags.append("over_generic_name")

        return max(score, 0), flags

    def _context_evidence(self, short_desc: str, long_desc: str, block_score: float = None):
        score = 0
        flags = []

        short_desc = self._clean_text(short_desc)
        long_desc = self._clean_text(long_desc)

        if short_desc:
            score += 1
        if long_desc:
            if len(long_desc) > 80:
                score += 3
            else:
                score += 1

        if not short_desc and not long_desc:
            flags.append("no_description")

        low = self._normalize(long_desc)
        if any(x in low for x in [
            "descubre", "sumérgete", "sumergite", "vive una experiencia",
            "no te pierdas", "te sorprenderá"
        ]):
            score -= 1
            flags.append("editorial_tone")

        if block_score is not None:
            if block_score >= 5:
                score += 2
            elif block_score >= 3:
                score += 1
            else:
                score -= 1
                flags.append("weak_block_context")

        return max(score, 0), flags

    def _structure_evidence(self, entity: dict):
        score = 0
        flags = []

        if entity.get("url"):
            score += 2

        related = entity.get("relatedUrls", [])
        if related:
            score += 1

        coords = entity.get("coordinates") or {}
        if coords.get("lat") is not None and coords.get("lng") is not None:
            score += 2

        if entity.get("address"):
            score += 1

        if entity.get("phone"):
            score += 1

        if entity.get("email"):
            score += 1

        images = entity.get("images", [])
        if isinstance(images, list) and images:
            score += 2
        elif entity.get("image") or entity.get("mainImage"):
            score += 2

        return score, flags

    def _consistency_evidence(self, label: str, related_urls):
        score = 0
        flags = []

        tokens = [t for t in self._tokens(label) if len(t) > 3]
        urls = related_urls or []

        if not urls:
            return 0, ["no_related_urls"]

        match_count = 0

        for u in urls:
            slug_tokens = self._slug_tokens(u)
            if any(t in slug_tokens for t in tokens):
                match_count += 1

        if match_count > 0:
            score += 2
        else:
            score -= 1
            flags.append("low_url_affinity")

        if len(urls) > 5 and match_count <= 1:
            score -= 1
            flags.append("noisy_related_urls")

        return max(score, 0), flags

    def _ontology_evidence(self, types):
        score = 0
        flags = []

        types = self._as_list(types)

        if any(t in self.strong_types for t in types):
            score += 3
        elif "Place" in types:
            score += 1
        else:
            flags.append("weak_type_signal")

        return score, flags

    # =========================================================
    # API
    # =========================================================

    def evaluate(self, entity: dict, block_score: float = None):
        label = (
            entity.get("label")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("name")
            or ""
        )

        short_desc = entity.get("short_description", "")
        long_desc = entity.get("long_description", "")
        related_urls = entity.get("relatedUrls", [])
        types = entity.get("type") or entity.get("types") or entity.get("class") or []

        flags = []
        total = 0

        s, f = self._name_evidence(label)
        total += s
        flags.extend(f)

        s, f = self._context_evidence(short_desc, long_desc, block_score=block_score)
        total += s
        flags.extend(f)

        s, f = self._structure_evidence(entity)
        total += s
        flags.extend(f)

        s, f = self._consistency_evidence(label, related_urls)
        total += s
        flags.extend(f)

        s, f = self._ontology_evidence(types)
        total += s
        flags.extend(f)

        total = max(0, min(15, round(total, 2)))

        if total >= 9:
            decision = "keep"
        elif total >= 5:
            decision = "review"
        else:
            decision = "discard"

        return {
            "evidenceScore": total,
            "evidenceFlags": sorted(set(flags)),
            "evidenceDecision": decision,
        }