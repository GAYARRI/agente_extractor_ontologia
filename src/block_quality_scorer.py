# src/block_quality_scorer.py

import re


class BlockQualityScorer:
    def __init__(self):
        self.navigation_terms = {
            "inicio", "home", "menu", "menú", "contacto", "privacy", "privacidad",
            "cookies", "aviso legal", "legal", "mapa web", "sitemap",
            "facebook", "instagram", "twitter", "youtube", "linkedin",
            "leer más", "mostrar más", "ver más", "more", "read more"
        }

    def _normalize(self, text: str) -> str:
        text = (text or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    def _tokens(self, text: str):
        return [t for t in re.split(r"[^\wáéíóúñü]+", self._normalize(text)) if t]

    def _link_density_estimate(self, text: str) -> float:
        """
        Aproximación simple: si hay muchas frases cortas repetidas, suele ser bloque navegación/listado.
        """
        parts = [p.strip() for p in re.split(r"[|•·\-–—/]+", text or "") if p.strip()]
        if not parts:
            return 0.0

        short_parts = sum(1 for p in parts if len(p.split()) <= 4)
        return short_parts / max(len(parts), 1)

    def evaluate(self, text: str, html: str = ""):
        score = 0
        flags = []

        norm = self._normalize(text)
        tokens = self._tokens(text)
        n_tokens = len(tokens)

        if not norm:
            return {
                "score": 0,
                "decision": "discard",
                "flags": ["empty_block"]
            }

        # longitud
        if n_tokens >= 40:
            score += 3
        elif n_tokens >= 20:
            score += 2
        elif n_tokens >= 10:
            score += 1
        else:
            score -= 2
            flags.append("too_short")

        # densidad semántica aproximada
        unique_ratio = len(set(tokens)) / max(len(tokens), 1)
        if unique_ratio > 0.6:
            score += 1
        elif unique_ratio < 0.35:
            score -= 1
            flags.append("low_lexical_diversity")

        # señales de navegación
        nav_hits = sum(1 for term in self.navigation_terms if term in norm)
        if nav_hits >= 3:
            score -= 3
            flags.append("navigation_like")
        elif nav_hits == 2:
            score -= 2
            flags.append("some_navigation_noise")

        # demasiada densidad de trozos cortos
        density = self._link_density_estimate(text)
        if density > 0.7:
            score -= 3
            flags.append("link_list_like")
        elif density > 0.5:
            score -= 1
            flags.append("partly_list_like")

        # presencia de puntuación explicativa/narrativa
        if re.search(r"[.:;]", text or ""):
            score += 1

        # señales de información útil
        if re.search(r"\b\d{4}\b", text or ""):
            score += 0.5
        if re.search(r"\bhttps?://", text or "", re.IGNORECASE):
            score += 0.5
        if re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text or ""):
            score += 0.5

        score = max(0, min(10, round(score, 2)))

        if score >= 5:
            decision = "keep"
        elif score >= 3:
            decision = "review"
        else:
            decision = "discard"

        return {
            "score": score,
            "decision": decision,
            "flags": list(set(flags)),
        }