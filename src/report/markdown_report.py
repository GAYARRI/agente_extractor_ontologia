# src/report/markdown_report.py

import re
from typing import Any, List


class EntitiesReporter:
    def __init__(self, ontology_index=None):
        self.ontology_index = ontology_index

    # =========================
    # Helpers
    # =========================

    def _normalize_space(self, text: str) -> str:
        text = text or ""
        return re.sub(r"\s+", " ", str(text)).strip()

    def _as_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def _dedupe_preserve_order(self, values: List[Any]) -> List[Any]:
        seen = set()
        out = []
        for v in values:
            key = str(v).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(v)
        return out

    def _clean_text(self, value: str) -> str:
        v = self._normalize_space(value)
        if not v:
            return ""

        noisy_markers = [
            " Leer más",
            " leer más",
            " Mostrar más",
            " mostrar más",
        ]

        for marker in noisy_markers:
            idx = v.find(marker)
            if idx > 0:
                v = v[:idx].strip(" -|,.;:")

        return v.strip()

    def _clean_multiline_text(self, value: str) -> str:
        if not value:
            return ""
        parts = [self._clean_text(p) for p in str(value).splitlines()]
        parts = [p for p in parts if p]
        parts = self._dedupe_preserve_order(parts)
        return "\n".join(parts)

    def _is_bad_name(self, value: str) -> bool:
        v = self._clean_text(value)
        vl = v.lower()

        if not v:
            return True

        bad_exact = {
            "comer y salir en sevilla - visita sevilla",
            "saborea sevilla barrio a barrio",
            "visita sevilla",
            "mainimage",
            "image",
            "consejos, rutas y curiosidades gastronómicas",
        }
        if vl in bad_exact:
            return True

        if re.fullmatch(r"\d+[_-]?", v):
            return True
        if re.fullmatch(r"[A-Za-z]?\d+[_-]?[A-Za-z]?", v):
            return True

        bad_fragments = [
            "leer más",
            "mostrar más",
            "ruta gastro",
            "descubre sevilla",
            "bajo el cielo de sevilla",
            "comer y salir en sevilla",
            "saborea sevilla",
            "visita sevilla",
            "consejos, rutas",
        ]
        return any(b in vl for b in bad_fragments)

    def _choose_display_name(self, entity: dict) -> str:
        label = self._clean_text(entity.get("label", ""))
        entity_name = self._clean_text(entity.get("entity_name", ""))
        entity_base = self._clean_text(entity.get("entity", ""))

        raw_name = entity.get("name", "")
        name_candidates = self._as_list(raw_name)
        name_candidates = [self._clean_text(n) for n in name_candidates if self._clean_text(n)]

        preferred = [label, entity_name, entity_base] + name_candidates

        for candidate in preferred:
            if candidate and not self._is_bad_name(candidate):
                return candidate

        for candidate in preferred:
            if candidate:
                return candidate

        return "Entidad"

    def _extract_types(self, entity: dict) -> List[str]:
        values = []
        values.extend(self._as_list(entity.get("type")))
        values.extend(self._as_list(entity.get("class")))

        cleaned = []
        for v in values:
            txt = self._normalize_space(str(v))
            if txt:
                cleaned.append(txt)

        return self._dedupe_preserve_order(cleaned)

    def _extract_related_urls(self, entity: dict) -> List[str]:
        raw = entity.get("relatedUrls", "")
        items = []

        if isinstance(raw, list):
            items.extend(raw)
        elif isinstance(raw, str):
            if "|" in raw:
                items.extend([x.strip() for x in raw.split("|")])
            elif "\n" in raw:
                items.extend([x.strip() for x in raw.splitlines()])
            elif raw.strip():
                items.append(raw.strip())

        return self._dedupe_preserve_order(items)

    def _extract_images(self, entity: dict) -> List[str]:
        props = entity.get("properties", {}) or {}

        candidates = [
            entity.get("image", ""),
            entity.get("mainImage", ""),
            props.get("image", ""),
            props.get("mainImage", ""),
        ]

        cleaned = []
        for c in candidates:
            c = self._clean_text(c)
            if not c:
                continue
            if c.lower() in {"image", "mainimage"}:
                continue
            cleaned.append(c)

        return self._dedupe_preserve_order(cleaned)

    def _entity_to_markdown(self, entity: dict) -> str:
        name = self._choose_display_name(entity)
        types_ = self._extract_types(entity)

        score = entity.get("score", "")
        source_url = self._clean_text(entity.get("sourceUrl", ""))
        url = self._clean_text(entity.get("url", ""))
        related_urls = self._extract_related_urls(entity)

        short_description = self._clean_text(entity.get("short_description", ""))
        long_description = self._clean_text(entity.get("long_description", ""))
        description = self._clean_multiline_text(entity.get("description", ""))
        address = self._clean_text(entity.get("address", ""))
        phone = self._clean_text(entity.get("phone", ""))
        email = self._clean_text(entity.get("email", ""))
        wikidata_id = self._clean_text(entity.get("wikidata_id", ""))

        images = self._extract_images(entity)

        coords = entity.get("coordinates") or {}
        lat = coords.get("lat")
        lng = coords.get("lng")

        lines = []
        lines.append(f"## {name}")
        lines.append("")

        if types_:
            lines.append(f"**type:** {', '.join(types_)}")
        if score not in ("", None):
            lines.append(f"**score:** {score}")
        if source_url:
            lines.append(f"**sourceUrl:** {source_url}")
        if url:
            lines.append(f"**url:** {url}")
        if related_urls:
            lines.append("**relatedUrls:**")
            for rel in related_urls:
                lines.append(f"- {rel}")
        if address:
            lines.append(f"**address:** {address}")
        if phone:
            lines.append(f"**phone:** {phone}")
        if email:
            lines.append(f"**email:** {email}")
        if lat not in (None, "") or lng not in (None, ""):
            lines.append(f"**coordinates:** lat={lat}, lng={lng}")
        if wikidata_id:
            lines.append(f"**wikidataId:** {wikidata_id}")
        if images:
            lines.append("**images:**")
            for img in images:
                lines.append(f"- {img}")
        if short_description:
            lines.append(f"**shortDescription:** {short_description}")
        if long_description:
            lines.append(f"**longDescription:** {long_description}")
        if description:
            lines.append(f"**description:** {description}")

        lines.append("")
        return "\n".join(lines)

    # =========================
    # API pública
    # =========================

    def generate_markdown_report(self, entities: list, output_path: str = "entities_report.md"):
        lines = []
        lines.append("# Knowledge Graph")
        lines.append(f"Total de entidades: {len(entities)}")
        lines.append("")

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            lines.append(self._entity_to_markdown(entity))

        content = "\n".join(lines).strip() + "\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)