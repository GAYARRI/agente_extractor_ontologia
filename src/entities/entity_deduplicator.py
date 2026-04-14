from __future__ import annotations

from typing import Any, Dict, List


class EntityDeduplicator:
    """
    Deduplicador robusto.

    Soporta:
    - strings
    - dicts de entidad
    - listas/tuplas

    Si recibe dicts, usa como clave principal:
    - name
    - entity_name
    - entity
    - label

    y conserva la versión más informativa.
    """

    def __init__(self):
        pass

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

    def _entity_key(self, entity: Any) -> str:
        return self._entity_name(entity).lower().strip()

    def _entity_score(self, entity: Any) -> float:
        if not isinstance(entity, dict):
            return 0.0

        for key in ("final_score", "score", "qualityScore", "semantic_similarity", "name_similarity"):
            value = entity.get(key)
            try:
                if value is not None:
                    return float(value)
            except Exception:
                continue

        return 0.0

    def _entity_info_weight(self, entity: Any) -> int:
        """
        Cuanto más informativa sea la entidad, más peso.
        """
        if not isinstance(entity, dict):
            return len(self._to_scalar_text(entity))

        weight = 0

        for field in ("description", "short_description", "long_description", "address", "phone", "email", "image", "mainImage"):
            value = entity.get(field)
            if isinstance(value, str) and value.strip():
                weight += 1

        props = entity.get("properties")
        if isinstance(props, dict) and props:
            weight += len([k for k, v in props.items() if v not in (None, "", [], {})])

        related = entity.get("relatedUrls")
        if isinstance(related, list):
            weight += len(related)

        name = self._entity_name(entity)
        weight += len(name)

        return weight

    def _choose_best(self, current: Any, candidate: Any) -> Any:
        """
        Si dos entidades tienen la misma clave:
        - preferir dict frente a string
        - preferir mayor score
        - si empatan, preferir la más informativa
        """
        if isinstance(current, dict) and not isinstance(candidate, dict):
            return current

        if isinstance(candidate, dict) and not isinstance(current, dict):
            return candidate

        current_score = self._entity_score(current)
        candidate_score = self._entity_score(candidate)

        if candidate_score > current_score:
            return candidate
        if current_score > candidate_score:
            return current

        current_weight = self._entity_info_weight(current)
        candidate_weight = self._entity_info_weight(candidate)

        if candidate_weight > current_weight:
            return candidate

        return current

    # =========================================================
    # API pública
    # =========================================================

    def deduplicate(self, entities: List[Any]) -> List[Any]:
        by_key: Dict[str, Any] = {}
        ordered_keys: List[str] = []

        for e in entities or []:
            key = self._entity_key(e)

            if not key:
                continue

            if key not in by_key:
                by_key[key] = e
                ordered_keys.append(key)
            else:
                by_key[key] = self._choose_best(by_key[key], e)

        return [by_key[k] for k in ordered_keys]