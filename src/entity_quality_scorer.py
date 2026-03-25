# src/entity_quality_scorer.py

import re
from urllib.parse import urlparse


class EntityQualityScorer:
    def __init__(self):
        self.stop_tokens = {
            "de", "la", "el", "los", "las", "en", "y", "a", "del"
        }

    # =========================================================
    # Helpers
    # =========================================================

    def _normalize(self, text: str) -> str:
        text = (text or "").lower().strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _tokenize(self, text: str):
        text = self._normalize(text)
        return [t for t in re.split(r"[^\wáéíóúñü]+", text) if t]

    def _slug_tokens(self, url: str):
        try:
            path = urlparse(url).path.lower()
        except Exception:
            return []

        return [t for t in re.split(r"[^\w]+", path) if t]

    def _clean_text(self, text: str):
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text

    # =========================================================
    # SCORING COMPONENTS
    # =========================================================

    def _score_name(self, label: str):
        tokens = self._tokenize(label)
        score = 0
        flags = []

        if not tokens:
            return -5, ["empty_name"]

        # longitud razonable
        if 2 <= len(tokens) <= 6:
            score += 2
        elif len(tokens) == 1:
            score -= 1
            flags.append("too_generic_name")
        elif len(tokens) > 8:
            score -= 1
            flags.append("too_long_name")

        # tokens no triviales
        meaningful = [t for t in tokens if t not in self.stop_tokens]
        if len(meaningful) >= 2:
            score += 1
        else:
            score -= 1
            flags.append("low_semantic_density")

        return score, flags

    def _score_description(self, short_desc, long_desc):
        score = 0
        flags = []

        short_desc = self._clean_text(short_desc)
        long_desc = self._clean_text(long_desc)

        if short_desc:
            score += 1

        if long_desc:
            if len(long_desc) > 80:
                score += 2
            else:
                score += 1

        if not short_desc and not long_desc:
            score -= 2
            flags.append("no_description")

        # detectar texto editorial genérico
        low = long_desc.lower()
        if any(x in low for x in [
            "descubre", "sumérgete", "vive", "experiencia única",
            "no te pierdas", "te sorprenderá"
        ]):
            score -= 1
            flags.append("editorial_text")

        return score, flags

    def _score_urls(self, label, related_urls):
        score = 0
        flags = []

        tokens = self._tokenize(label)
        tokens = [t for t in tokens if len(t) > 3]

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

        # muchas URLs pero poco match → sospechoso
        if len(urls) > 5 and match_count <= 1:
            score -= 1
            flags.append("noisy_urls")

        return score, flags

    def _score_properties(self, entity):
        score = 0
        flags = []

        if entity.get("url"):
            score += 1

        coords = entity.get("coordinates") or {}
        if coords.get("lat") and coords.get("lng"):
            score += 1

        if entity.get("address"):
            score += 0.5

        if entity.get("phone"):
            score += 0.5

        if entity.get("email"):
            score += 0.5

        return score, flags

    def _score_type(self, types):
        score = 0

        types = types or []

        strong_types = {
            "Event",
            "TouristAttraction",
            "Organization",
            "LocalBusiness",
            "Route"
        }

        if any(t in strong_types for t in types):
            score += 2
        elif "Place" in types:
            score += 1

        return score, []

    def _score_name_specificity(self, label):
        tokens = self._tokenize(label)

        if len(tokens) == 1:
            return -2, ["too_generic"]

        if len(tokens) == 2:
            return 0, []

        return 1, []

    # =========================================================
    # MAIN API
    # =========================================================

    def evaluate(self, entity: dict):
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
        types = entity.get("type") or entity.get("types") or []

        total_score = 0
        flags = []

        for fn in [
            lambda: self._score_name(label),
            lambda: self._score_name_specificity(label),
            lambda: self._score_description(short_desc, long_desc),
            lambda: self._score_urls(label, related_urls),
            lambda: self._score_properties(entity),
            lambda: self._score_type(types),
        ]:
            s, f = fn()
            total_score += s
            flags.extend(f)

        # normalizar score
        total_score = max(0, min(10, round(total_score, 2)))

        # decisión
        if total_score >= 6:
            decision = "keep"
        elif total_score >= 3:
            decision = "review"
        else:
            decision = "discard"

        return {
            "score": total_score,
            "flags": list(set(flags)),
            "decision": decision
        }