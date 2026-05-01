import re


class DescriptionExtractor:
    def _build_entity_local_text(self, entity, text):
        entity = entity if isinstance(entity, dict) else {}
        parts = []

        signals = entity.get("html_context_signals")
        if isinstance(signals, dict):
            heading = str(signals.get("heading") or "").strip()
            if heading:
                parts.append(heading)

        source_text = str(entity.get("source_text") or "").strip()
        if source_text:
            parts.append(source_text)

        merged = " ".join(part for part in parts if part).strip()
        if merged:
            return merged

        return str(text or "").strip()

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
            "Ç?rea profesional",
            "Area profesional",
            "Mapas y guÇðas",
            "Mapas y guias",
            "Qué hacer",
            "Que hacer",
            "Planes para inspirarte",
            "Compartir",
            "Guardar favorito",
            "Eliminar favorito",
            "Ir a mis favoritos",
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
        text = re.sub(r"\b(compartir|guardar favorito|eliminar favorito|ir a mis favoritos)\b.*$", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\b(qu[eé]\s+hacer|planes\s+para\s+inspirarte)\b.*$", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"\b([A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'’\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'’\-]+){1,5})\b(?:\s+\1\b)+", r"\1", text).strip()
        return text

    def extract(self, entity, text):
        text = self._build_entity_local_text(entity, text)
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
