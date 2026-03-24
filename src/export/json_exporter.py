# src/export/json_exporter.py

import json
import re


class JSONExporter:
    def __init__(self):
        pass

    # -------------------------
    # Helpers
    # -------------------------

    def _normalize_space(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    def _clean_text(self, value: str) -> str:
        v = self._normalize_space(value)
        if not v:
            return ""

        for marker in [" Leer más", " leer más", " Mostrar más", " mostrar más"]:
            idx = v.find(marker)
            if idx > 0:
                v = v[:idx].strip(" -|,.;:")

        return v.strip()

    def _as_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def _dedupe(self, values):
        seen = set()
        out = []
        for v in values:
            key = str(v).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(v)
        return out

    def _choose_name(self, entity):
        for key in ["label", "entity_name", "entity", "name"]:
            val = self._clean_text(entity.get(key, ""))
            if val:
                return val
        return "Entidad"

    def _extract_images(self, entity):

        props = entity.get("properties", {}) or {}

        candidates = [
            entity.get("image", ""),
            entity.get("mainImage", ""),
            props.get("image", ""),
            props.get("mainImage", ""),
            props.get("additionalImages", []),
        ]

        flat = []

        for c in candidates:
            if not c:
                continue

            if isinstance(c, list):
                flat.extend(c)
                continue

            c = str(c).strip()

            # Caso: lista serializada como string Python
            if c.startswith("[") and c.endswith("]"):
                inner = c[1:-1].strip()
                parts = [p.strip(" '\"") for p in inner.split(",") if p.strip(" '\"")]
                flat.extend(parts)
                continue

            # Caso: lista serializada con separador |
            if "|" in c:
                flat.extend([x.strip() for x in c.split("|") if x.strip()])
                continue

            flat.append(c)

        cleaned = []
        seen = set()

        for img in flat:
            img = self._clean_text(img)
            if not img:
                continue

            low = img.lower()

            if low in {"image", "mainimage"}:
                continue

            if not (low.startswith("http://") or low.startswith("https://")):
                continue

            # filtros decorativos / globales
            bad_patterns = [
                "separador",
                "separator",
                "logo",
                "icon",
                "banner",
                "placeholder",
                "header",
                "footer",
                "share",
                "social",
            ]
            if any(b in low for b in bad_patterns):
                continue

            if img in seen:
                continue

            seen.add(img)
            cleaned.append(img)

        return cleaned    
        



    def _extract_types(self, entity):
        types = []
        types.extend(self._as_list(entity.get("type")))
        types.extend(self._as_list(entity.get("class")))
        return self._dedupe([self._normalize_space(t) for t in types if t])

    def _extract_related_urls(self, entity):
        raw = entity.get("relatedUrls", "")
        urls = []

        if isinstance(raw, list):
            urls.extend(raw)
        elif isinstance(raw, str):
            if "|" in raw:
                urls.extend([x.strip() for x in raw.split("|")])
            elif "\n" in raw:
                urls.extend([x.strip() for x in raw.splitlines()])
            elif raw.strip():
                urls.append(raw.strip())

        return self._dedupe(urls)

    # -------------------------
    # Conversión
    # -------------------------

    def entity_to_dict(self, entity: dict) -> dict:
        coords = entity.get("coordinates") or {}

        return {
            "name": self._choose_name(entity),
            "types": self._extract_types(entity),
            "score": entity.get("score"),

            "sourceUrl": self._clean_text(entity.get("sourceUrl")),
            "url": self._clean_text(entity.get("url")),

            "relatedUrls": self._extract_related_urls(entity),

            "address": self._clean_text(entity.get("address")),
            "phone": self._clean_text(entity.get("phone")),
            "email": self._clean_text(entity.get("email")),

            "coordinates": {
                "lat": coords.get("lat"),
                "lng": coords.get("lng"),
            },

            "shortDescription": self._clean_text(entity.get("short_description")),
            "longDescription": self._clean_text(entity.get("long_description")),
            "description": self._clean_text(entity.get("description")),

            "images": self._extract_images(entity),

            "wikidataId": self._clean_text(entity.get("wikidata_id")),
        }

    # -------------------------
    # Export
    # -------------------------

    def export(self, entities: list, output_path="entities.json"):
        data = [self.entity_to_dict(e) for e in entities if isinstance(e, dict)]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return data