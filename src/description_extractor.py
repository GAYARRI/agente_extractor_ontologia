import re


class DescriptionExtractor:
    def _clean_description_text(self, text):
        text = str(text or "").strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            return ""

        leading_patterns = [
            r"^\s*ir al contenido\s+",
            r"^\s*reserva tu actividad\s+",
        ]
        for pattern in leading_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

        cut_markers = [
            "Ayuntamiento de Pamplona 31001",
            "Descubre Pamplona",
            "Convention Bureau",
            "Área profesional",
            "Area profesional",
            "Mapas y guías",
            "Mapas y guias",
        ]
        low = text.lower()
        cut_points = []
        for marker in cut_markers:
            idx = low.find(marker.lower())
            if idx > 0:
                cut_points.append(idx)

        if cut_points:
            text = text[: min(cut_points)].strip()

        text = re.sub(r"^(ir al contenido|reserva tu actividad)\b", "", text, flags=re.IGNORECASE).strip()
        return text

    def extract(self, entity, text):
        text = self._clean_description_text(text)

        short = self._get_first_sentence(text)
        long = self._get_long_description(text)

        return {
            "short_description": short,
            "long_description": long,
        }

    def _get_first_sentence(self, text):
        text = self._clean_description_text(text)
        parts = [part.strip() for part in text.split(".") if part.strip()]

        if parts:
            return parts[0]

        return text[:120]

    def _get_long_description(self, text):
        text = self._clean_description_text(text)
        return text[:300].strip()
