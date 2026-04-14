from __future__ import annotations

import re
from typing import Any, Dict, List


class EntityExpander:
    """
    Expande / enriquece entidades sin romper compatibilidad con formatos legacy.

    Soporta entradas:
    - str
    - dict
    - list / tuple

    Si recibe dicts, preserva la estructura.
    Si recibe strings, devuelve strings.
    """

    def __init__(self):
        # conectores válidos dentro de nombres turísticos
        self.valid_connectors = {
            "de", "del", "la", "las", "el", "los", "y", "e"
        }

        # colas narrativas que sí conviene cortar
        self.trailing_noise = {
            "es", "son", "fue", "fueron", "era", "eran",
            "que", "donde", "cuando", "como", "aunque",
            "uno", "una", "unos", "unas",
            "este", "esta", "estos", "estas",
            "su", "sus", "un", "una",
            "a", "al",
            "e", "y",
        }

        # terminaciones que no deben quedar al final
        self.invalid_trailing_endings = {
            "de", "del", "la", "las", "el", "los", "e", "y", "a", "al"
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
            for key in ("name", "entity_name", "entity", "label", "text", "content", "source_text"):
                v = value.get(key)
                if isinstance(v, str) and v.strip():
                    parts.append(v.strip())
                elif isinstance(v, (list, tuple)):
                    parts.extend(str(x).strip() for x in v if x is not None and str(x).strip())
            return " ".join(parts).strip()

        if isinstance(value, (list, tuple)):
            return " ".join(str(x).strip() for x in value if x is not None and str(x).strip()).strip()

        return str(value).strip()

    def _entity_name(self, entity: Any) -> str:
        if isinstance(entity, dict):
            return (
                str(entity.get("name") or "").strip()
                or str(entity.get("entity_name") or "").strip()
                or str(entity.get("entity") or "").strip()
                or str(entity.get("label") or "").strip()
            )
        return self._to_scalar_text(entity)

    def _clean_text(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)
        return text.strip(" ,.;:|-")

    def _trim_trailing_noise(self, entity_text: str) -> str:
        words = entity_text.split()

        # quitar cola narrativa
        while words and words[-1].lower() in self.trailing_noise:
            words.pop()

        # evitar finales rotos tipo "Museo de"
        while words and words[-1].lower() in self.invalid_trailing_endings:
            words.pop()

        # segunda pasada por si queda otra cola mala
        while words and words[-1].lower() in self.trailing_noise:
            words.pop()

        return " ".join(words).strip()

    def _expand_text(self, entity_text: str, text: str) -> str:
        """
        Expansión conservadora:
        - limpia
        - corta colas narrativas
        - no destruye conectores válidos del nombre
        """
        entity_text = self._clean_text(entity_text)
        if not entity_text:
            return entity_text

        words = entity_text.split()
        if not words:
            return ""

        # quitar solo basura al principio, no conectores estructurales válidos internos
        while words and words[0].lower() in {"un", "una", "unos", "unas"}:
            words.pop(0)

        entity_text = " ".join(words).strip()
        entity_text = self._clean_text(entity_text)

        entity_text = self._trim_trailing_noise(entity_text)
        entity_text = self._clean_text(entity_text)

        # no dejar entidades vacías o de una sola palabra demasiado genérica
        if not entity_text:
            return ""

        return entity_text

    def _expand_dict_entity(self, entity: Dict[str, Any], text: str) -> Dict[str, Any] | None:
        item = dict(entity)

        visible_name = self._entity_name(item)
        visible_name = self._expand_text(visible_name, text)

        if not visible_name:
            return None

        # sincronizar campos principales
        item["entity"] = visible_name
        item["entity_name"] = visible_name
        item["label"] = visible_name
        item["name"] = visible_name

        # source_text como string siempre
        if "source_text" in item:
            item["source_text"] = self._to_scalar_text(item.get("source_text"))

        return item

    # =========================================================
    # API pública
    # =========================================================

    def expand(self, entities: List[Any], text: str) -> List[Any]:
        expanded: List[Any] = []
        text = self._to_scalar_text(text)

        for entity in entities or []:
            if isinstance(entity, dict):
                item = self._expand_dict_entity(entity, text)
                if item is None:
                    continue
                expanded.append(item)
                continue

            if isinstance(entity, str):
                value = self._expand_text(entity, text)
                if value:
                    expanded.append(value)
                continue

            value = self._to_scalar_text(entity)
            value = self._expand_text(value, text)
            if value:
                expanded.append(value)

        return expanded