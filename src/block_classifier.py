import re


class BlockClassifier:
    def __init__(self):
        self.collective_patterns = [
            r"\bdesde\b.*\bhasta\b",
            r"\bentre\b.*\by\b",
            r"\bcomo\b\s+.+",
            r"\brincones\b",
            r"\bplayas vírgenes\b",
            r"\bplayas naturales\b",
            r"\bconjunto de\b",
            r"\bvarias\b",
            r"\bdistintas\b",
            r"\balgunas de\b",
            r"\buna selección de\b",
            r"\blista de\b",
            r"\bgrupo de\b",
        ]

        self.collective_headings = {
            "playas",
            "museos",
            "rutas",
            "hoteles",
            "restaurantes",
            "puertos deportivos",
            "naturaleza",
            "actividades",
            "lugares de interés",
            "qué ver",
            "qué hacer",
        }

    def _normalize(self, text: str) -> str:
        return " ".join(text.strip().lower().split())

    def classify_block(self, block: dict) -> dict:
        heading = self._normalize(block.get("heading", ""))
        text = self._normalize(block.get("text", ""))

        score = 0.0
        reasons = []

        if heading in self.collective_headings:
            score += 0.5
            reasons.append("heading_colectivo")

        for pattern in self.collective_patterns:
            if re.search(pattern, text):
                score += 0.4
                reasons.append(f"pattern:{pattern}")

        # si el heading es corto y genérico
        if heading and len(heading.split()) <= 3 and any(word in heading for word in ["playas", "museos", "rutas", "actividades"]):
            score += 0.2
            reasons.append("heading_generico")

        # si parece una ficha específica, restar
        if heading and len(heading.split()) >= 2 and heading not in self.collective_headings:
            score -= 0.2
            reasons.append("heading_especifico")

        is_collective = score >= 0.5

        return {
            "is_collective": is_collective,
            "score": score,
            "reasons": reasons,
        }