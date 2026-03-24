# src/entity_description_consolidator.py

import re
import unicodedata


class EntityDescriptionConsolidator:
    def __init__(self):
        pass

    # =========================================================
    # Helpers
    # =========================================================

    def _normalize_entity_key(self, text: str) -> str:
        text = text or ""
        text = text.strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _as_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _dedupe_preserve_order(self, values):
        seen = set()
        out = []
        for v in values:
            key = str(v).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(v)
        return out

    def _clean_text(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)

        noisy_markers = [
            " Leer más",
            " leer más",
            " Mostrar más",
            " mostrar más",
        ]
        for marker in noisy_markers:
            idx = text.find(marker)
            if idx > 0:
                text = text[:idx].strip(" -|,.;:")

        return text.strip()

    def _normalize_related_urls(self, value):
        items = []

        if isinstance(value, list):
            items.extend(value)
        elif isinstance(value, str):
            if "|" in value:
                items.extend([x.strip() for x in value.split("|") if x.strip()])
            elif "\n" in value:
                items.extend([x.strip() for x in value.splitlines() if x.strip()])
            elif value.strip():
                items.append(value.strip())

        items = [x for x in items if str(x).startswith("http://") or str(x).startswith("https://")]
        return self._dedupe_preserve_order(items)

    def _merge_properties(self, base: dict, extra: dict) -> dict:
        out = dict(base or {})

        for k, v in (extra or {}).items():
            if v in (None, "", [], {}):
                continue

            if k not in out or out[k] in (None, "", [], {}):
                out[k] = v
                continue

            if out[k] == v:
                continue

            old_val = out[k]
            old_list = old_val if isinstance(old_val, list) else [old_val]
            new_list = v if isinstance(v, list) else [v]
            out[k] = self._dedupe_preserve_order(old_list + new_list)

        return out

    def _merge_field(self, current, incoming):
        if current in (None, "", [], {}):
            return incoming
        return current

    def _merge_text_field(self, current: str, incoming: str) -> str:
        current = self._clean_text(current or "")
        incoming = self._clean_text(incoming or "")

        if not current:
            return incoming
        if not incoming:
            return current

        # conservar el más largo
        return incoming if len(incoming) > len(current) else current

    def _merge_coordinates(self, c1: dict, c2: dict) -> dict:
        c1 = c1 or {}
        c2 = c2 or {}

        lat1, lng1 = c1.get("lat"), c1.get("lng")
        lat2, lng2 = c2.get("lat"), c2.get("lng")

        if lat1 is not None and lng1 is not None:
            return {"lat": lat1, "lng": lng1}
        if lat2 is not None and lng2 is not None:
            return {"lat": lat2, "lng": lng2}

        return {"lat": None, "lng": None}

    # =========================================================
    # API pública
    # =========================================================

    def consolidate(self, all_results: list) -> list:
        """
        all_results puede venir como lista de:
        - entidades directas
        - resultados de página con {"entities": [...]}
        """
        entities = []

        for item in all_results or []:
            if not item:
                continue

            if isinstance(item, dict) and "entities" in item:
                ents = item.get("entities") or []
                for e in ents:
                    if isinstance(e, dict):
                        entities.append(e)
            elif isinstance(item, dict):
                entities.append(item)

        grouped = {}

        for e in entities:
            name = (
                e.get("entity_name")
                or e.get("entity")
                or e.get("label")
                or e.get("name")
                or ""
            ).strip()

            if not name:
                continue

            key = self._normalize_entity_key(name)

            if key not in grouped:
                grouped[key] = {
                    "entity": e.get("entity", name),
                    "entity_name": e.get("entity_name", name),
                    "label": e.get("label", name),
                    "name": e.get("name", name),
                    "class": e.get("class", ""),
                    "type": e.get("type", e.get("class", "")),
                    "score": e.get("score", 0.0),
                    "verisimilitude_score": e.get("verisimilitude_score", e.get("score", 0.0)),
                    "properties": e.get("properties", {}) or {},
                    "short_description": e.get("short_description", ""),
                    "long_description": e.get("long_description", ""),
                    "description": e.get("description", ""),
                    "address": e.get("address", ""),
                    "phone": e.get("phone", ""),
                    "email": e.get("email", ""),
                    "coordinates": e.get("coordinates", {"lat": None, "lng": None}),
                    "wikidata_id": e.get("wikidata_id", ""),
                    "sourceUrl": e.get("sourceUrl", ""),
                    "url": e.get("url", ""),
                    "relatedUrls": self._normalize_related_urls(e.get("relatedUrls", "")),
                    "image": e.get("image", ""),
                    "mainImage": e.get("mainImage", ""),
                }
                continue

            merged = grouped[key]

            merged["score"] = max(merged.get("score", 0.0), e.get("score", 0.0))
            merged["verisimilitude_score"] = max(
                merged.get("verisimilitude_score", 0.0),
                e.get("verisimilitude_score", e.get("score", 0.0))
            )

            if not merged.get("class") and e.get("class"):
                merged["class"] = e.get("class")

            if not merged.get("type") and e.get("type"):
                merged["type"] = e.get("type")

            merged["properties"] = self._merge_properties(
                merged.get("properties", {}),
                e.get("properties", {}) or {}
            )

            merged["short_description"] = self._merge_text_field(
                merged.get("short_description", ""),
                e.get("short_description", "")
            )

            merged["long_description"] = self._merge_text_field(
                merged.get("long_description", ""),
                e.get("long_description", "")
            )

            merged["description"] = self._merge_text_field(
                merged.get("description", ""),
                e.get("description", "")
            )

            merged["address"] = self._merge_text_field(
                merged.get("address", ""),
                e.get("address", "")
            )

            merged["phone"] = self._merge_field(
                merged.get("phone", ""),
                e.get("phone", "")
            )

            merged["email"] = self._merge_field(
                merged.get("email", ""),
                e.get("email", "")
            )

            merged["coordinates"] = self._merge_coordinates(
                merged.get("coordinates"),
                e.get("coordinates")
            )

            merged["wikidata_id"] = self._merge_field(
                merged.get("wikidata_id", ""),
                e.get("wikidata_id", "")
            )

            # >>> AQUÍ ESTABA TU PROBLEMA PRINCIPAL <<<
            merged["sourceUrl"] = self._merge_field(
                merged.get("sourceUrl", ""),
                e.get("sourceUrl", "")
            )

            merged["url"] = self._merge_field(
                merged.get("url", ""),
                e.get("url", "")
            )

            old_related = merged.get("relatedUrls", [])
            new_related = self._normalize_related_urls(e.get("relatedUrls", ""))
            merged["relatedUrls"] = self._dedupe_preserve_order(old_related + new_related)

            merged["image"] = self._merge_field(
                merged.get("image", ""),
                e.get("image", "")
            )

            merged["mainImage"] = self._merge_field(
                merged.get("mainImage", ""),
                e.get("mainImage", "")
            )

        return list(grouped.values())