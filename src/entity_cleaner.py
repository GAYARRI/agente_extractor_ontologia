from __future__ import annotations

import re
from typing import Any, Dict, List


class EntityCleaner:
    """
    Limpia entidades de forma robusta.

    Soporta entradas como:
    - str
    - dict
    - list / tuple
    """

    def __init__(self):
        self.noise_patterns = [
            r"^\s*$",
            r"^[\W_]+$",
            r"^\d+$",
            r"^[ivxlcdm]+$",
        ]

        self.bad_exact = {
            "leer",
            "ver más",
            "ver mas",
            "mostrar más",
            "mostrar mas",
            "share",
            "copy link",
            "conociendo",
            "descubre",
            "historia",
            "información",
            "informacion",
            "contenido",
            "inicio",
            "detalle",
            "detalles",
            "servicios",
            "actividad",
            "actividades",
            "visita",
            "visitas",
            "guía",
            "guia",
            "datos",
            "más",
            "mas",
            "en sevilla",
            "la sevilla",
            "sevilla cada",
            "el día mundial",
            "el dia mundial",
            "declarado patrimonio cultural inmaterial",
            "google analytics",
        }

        self.bad_prefixes = (
            "conoce ",
            "conociendo ",
            "descubre ",
            "historia de ",
            "información de ",
            "informacion de ",
            "visita ",
            "guía de ",
            "guia de ",
            "en ",
            "declarado ",
            "declarada ",
            "el día ",
            "el dia ",
        )

        self.bad_suffixes = (
            " leer",
            " ver más",
            " ver mas",
            " mostrar más",
            " mostrar mas",
        )

        self.generic_single_words = {
            "sevilla",
            "españa",
            "espana",
            "andalucía",
            "andalucia",
            "turismo",
            "cultura",
            "ocio",
            "agenda",
            "familia",
            "planes",
            "ruta",
            "rutas",
            "evento",
            "eventos",
            "monumentos",
            "museos",
            "barrios",
            "parques",
            "compras",
            "gastronomía",
            "gastronomia",
            "flamenco",
        }

        self.bad_contains = {
            "google analytics",
            "patrimonio cultural inmaterial",
            "sevilla cada",
        }

    # =========================================================
    # Helpers
    # =========================================================

    def _to_scalar_text(self, value: Any) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()

        if isinstance(value, dict):
            parts = []
            for key in ("name", "label", "entity_name", "entity", "text", "content", "source_text"):
                v = value.get(key)
                if isinstance(v, str) and v.strip():
                    parts.append(v.strip())
                elif isinstance(v, (list, tuple)):
                    parts.extend(str(x).strip() for x in v if x is not None and str(x).strip())
            return " ".join(parts).strip()

        if isinstance(value, (list, tuple)):
            return " ".join(str(x).strip() for x in value if x is not None and str(x).strip()).strip()

        return str(value).strip()

    def _clean_text(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text.strip(" \t\r\n,.;:|-")

    def _looks_like_bad_editorial(self, text: str) -> bool:
        low = (text or "").strip().lower()

        if not low:
            return True

        if low in self.bad_exact:
            return True

        if any(low.startswith(prefix) for prefix in self.bad_prefixes):
            return True

        if any(low.endswith(suffix) for suffix in self.bad_suffixes):
            return True

        if any(fragment in low for fragment in self.bad_contains):
            return True

        if len(low.split()) == 1 and low in self.generic_single_words:
            return True

        if low == low.lower() and len(low.split()) <= 3 and low in {
            "qué hacer", "que hacer", "durante tu estancia", "ideas y planes"
        }:
            return True

        return False

    def _is_noise(self, text: str) -> bool:
        low = (text or "").strip().lower()

        if not low:
            return True

        if self._looks_like_bad_editorial(low):
            return True

        for pattern in self.noise_patterns:
            if re.fullmatch(pattern, low):
                return True

        return False

    def _clean_dict_entity(self, entity: Dict[str, Any]) -> Dict[str, Any] | None:
        item = dict(entity)

        for field in ("entity", "entity_name", "label", "name", "source_text"):
            if field in item:
                item[field] = self._clean_text(self._to_scalar_text(item.get(field)))

        visible_name = (
            item.get("name")
            or item.get("entity_name")
            or item.get("entity")
            or item.get("label")
            or ""
        )
        visible_name = self._clean_text(visible_name)

        if self._is_noise(visible_name):
            return None

        item["entity"] = visible_name
        item["entity_name"] = visible_name
        item["label"] = visible_name
        item["name"] = visible_name

        return item

    # =========================================================
    # API pública
    # =========================================================

    def clean(self, entities: List[Any]) -> List[Any]:
        cleaned: List[Any] = []
        seen = set()

        for e in entities or []:
            if isinstance(e, str):
                text = self._clean_text(e)
                if self._is_noise(text):
                    continue

                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)

                cleaned.append(text)
                continue

            if isinstance(e, dict):
                item = self._clean_dict_entity(e)
                if item is None:
                    continue

                key = item["name"].lower()
                if key in seen:
                    continue
                seen.add(key)

                cleaned.append(item)
                continue

            text = self._clean_text(self._to_scalar_text(e))
            if self._is_noise(text):
                continue

            key = text.lower()
            if key in seen:
                continue
            seen.add(key)

            cleaned.append(text)

        return cleaned