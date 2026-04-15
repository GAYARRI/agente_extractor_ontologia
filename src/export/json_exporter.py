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
        if isinstance(value, tuple):
            return list(value)
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

    def _is_valid_image_url(self, img: str) -> bool:
        img = self._clean_text(img)
        if not img:
            return False

        low = img.lower()

        if low in {"image", "mainimage"}:
            return False

        if not (low.startswith("http://") or low.startswith("https://")):
            return False

        valid_exts = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"]
        if not any(ext in low for ext in valid_exts):
            return False

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
            "_next/static/",
            "_next/image?",
            "/static/media/",
            "financion",
            "favicon",
            "avatar",
            "sprite",
        ]
        if any(b in low for b in bad_patterns):
            return False

        if ".svg" in low:
            return False

        return True

    def _flatten_maybe_serialized_list(self, value):
        flat = []

        if not value:
            return flat

        if isinstance(value, list):
            for item in value:
                flat.extend(self._flatten_maybe_serialized_list(item))
            return flat

        if isinstance(value, tuple):
            for item in value:
                flat.extend(self._flatten_maybe_serialized_list(item))
            return flat

        value = str(value).strip()
        if not value:
            return flat

        # Caso: lista serializada como string Python
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if inner:
                parts = [p.strip(" '\"") for p in inner.split(",") if p.strip(" '\"")]
                flat.extend(parts)
            return flat

        # Caso: separador |
        if "|" in value:
            flat.extend([x.strip() for x in value.split("|") if x.strip()])
            return flat

        # Caso: multilínea
        if "\n" in value:
            flat.extend([x.strip() for x in value.splitlines() if x.strip()])
            return flat

        flat.append(value)
        return flat

    def _extract_images(self, entity):
        props = entity.get("properties", {}) or {}
        if not isinstance(props, dict):
            props = {}

        candidates = [
            entity.get("image", ""),
            entity.get("mainImage", ""),
            entity.get("images", []),
            entity.get("additionalImages", []),
            props.get("image", ""),
            props.get("mainImage", ""),
            props.get("additionalImages", []),
        ]

        flat = []
        for c in candidates:
            flat.extend(self._flatten_maybe_serialized_list(c))

        cleaned = []
        seen = set()

        for img in flat:
            img = self._clean_text(img)
            if not img:
                continue

            if not self._is_valid_image_url(img):
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
        types.extend(self._as_list(entity.get("types")))

        props = entity.get("properties", {}) or {}
        if isinstance(props, dict):
            types.extend(self._as_list(props.get("type")))

        cleaned = [self._normalize_space(t) for t in types if t]
        return self._dedupe(cleaned)

    def _extract_related_urls(self, entity):
        props = entity.get("properties", {}) or {}
        if not isinstance(props, dict):
            props = {}

        raw_values = [
            entity.get("relatedUrls", ""),
            props.get("relatedUrls", ""),
        ]

        urls = []
        for raw in raw_values:
            if isinstance(raw, list):
                urls.extend(raw)
            elif isinstance(raw, str):
                if "|" in raw:
                    urls.extend([x.strip() for x in raw.split("|")])
                elif "\n" in raw:
                    urls.extend([x.strip() for x in raw.splitlines()])
                elif raw.strip():
                    urls.append(raw.strip())

        urls = [self._clean_text(u) for u in urls if self._clean_text(u)]
        return self._dedupe(urls)

    def _extract_coordinates(self, entity):
        coords = entity.get("coordinates") or {}
        if not isinstance(coords, dict):
            coords = {}

        lat = coords.get("lat")
        lng = coords.get("lng")

        if lat in (None, ""):
            lat = entity.get("latitude")

        if lng in (None, ""):
            lng = entity.get("longitude")

        return {
            "lat": lat,
            "lng": lng,
        }

    # -------------------------
    # Conversión
    # -------------------------

    def entity_to_dict(self, entity: dict) -> dict:
        coords = self._extract_coordinates(entity)
        images = self._extract_images(entity)

        primary_image = images[0] if images else ""
        additional_images = images[1:] if len(images) > 1 else []

        wikidata_id = self._clean_text(
            entity.get("wikidata_id") or entity.get("wikidataId")
        )

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

            "image": primary_image,
            "mainImage": primary_image,
            "images": images,
            "additionalImages": additional_images,

            "wikidataId": wikidata_id,
        }

    # -------------------------
    # Export
    # -------------------------

    def export(self, entities: list, output_path="entities.json"):
        data = [self.entity_to_dict(e) for e in entities if isinstance(e, dict)]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return data