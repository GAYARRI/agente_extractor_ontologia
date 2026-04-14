from __future__ import annotations

import re
from typing import Any, Dict, List


class EntitySplitter:
    """
    Divide entidades compuestas sin romper compatibilidad con formatos legacy.

    Soporta:
    - str
    - dict
    - list
    - tuple

    Si recibe dicts, preserva la estructura y sincroniza:
    - entity
    - entity_name
    - label
    - name
    """

    def __init__(self):
        # Puedes ampliar este patrón con más eventos/nombres compuestos
        self.special_split_pattern = re.compile(
            r"(Semana Santa|Romería de Piedraescrita|Fiesta de la Chanfaina)",
            flags=re.IGNORECASE,
        )

        self.separator_pattern = re.compile(r"\s+\|\s+|\s+/\s+|\s+;\s+")
        self.max_parts = 5

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

    def _valid_part(self, text: str) -> bool:
        text = self._clean_text(text)
        if not text:
            return False
        if len(text) < 3:
            return False
        if re.fullmatch(r"[\W\d_]+", text):
            return False
        return True

    def _split_text(self, entity_text: str) -> List[str]:
        entity_text = self._clean_text(entity_text)
        if not entity_text:
            return []

        parts: List[str] = []

        # 1) split especial por entidades/eventos conocidos
        special_parts = self.special_split_pattern.split(entity_text)
        special_parts = [self._clean_text(p) for p in special_parts if self._valid_part(p)]

        if len(special_parts) > 1:
            parts.extend(special_parts)
        else:
            # 2) split genérico por separadores suaves
            generic_parts = self.separator_pattern.split(entity_text)
            generic_parts = [self._clean_text(p) for p in generic_parts if self._valid_part(p)]

            if len(generic_parts) > 1:
                parts.extend(generic_parts)
            else:
                parts.append(entity_text)

        # dedupe conservador preservando orden
        seen = set()
        out = []
        for p in parts[: self.max_parts]:
            key = p.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)

        return out

    def _clone_dict_entity(self, entity: Dict[str, Any], new_name: str) -> Dict[str, Any]:
        item = dict(entity)
        item["entity"] = new_name
        item["entity_name"] = new_name
        item["label"] = new_name
        item["name"] = new_name
        return item

    # =========================================================
    # API pública
    # =========================================================

    def split(self, entities: List[Any]) -> List[Any]:
        splitted: List[Any] = []

        for entity in entities or []:
            # Caso dict moderno
            if isinstance(entity, dict):
                base_name = self._entity_name(entity)
                parts = self._split_text(base_name)

                if not parts:
                    continue

                if len(parts) == 1:
                    splitted.append(self._clone_dict_entity(entity, parts[0]))
                else:
                    for part in parts:
                        splitted.append(self._clone_dict_entity(entity, part))
                continue

            # Caso string legacy
            if isinstance(entity, str):
                parts = self._split_text(entity)
                splitted.extend(parts)
                continue

            # Caso list/tuple/otros
            base_text = self._to_scalar_text(entity)
            parts = self._split_text(base_text)
            splitted.extend(parts)

        return splitted