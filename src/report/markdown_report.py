# src/report/markdown_report.py

import re


class EntitiesReporter:
    def __init__(self, ontology_index=None):
        self.ontology_index = ontology_index

    # =========================================================
    # Helpers
    # =========================================================

    def _clean_text(self, text):
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)
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

        items = [
            x for x in items
            if str(x).startswith("http://") or str(x).startswith("https://")
        ]
        return self._dedupe_preserve_order(items)

    def _pick_name(self, entity):
        return (
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or "Entidad sin nombre"
        )

    def _pick_types(self, entity):
        types = []

        if entity.get("types"):
            types.extend(self._as_list(entity.get("types")))

        if entity.get("type"):
            types.extend(self._as_list(entity.get("type")))

        if entity.get("class"):
            types.extend(self._as_list(entity.get("class")))

        if not types:
            return ["Place"]

        cleaned = []
        for t in types:
            t = self._clean_text(str(t))
            if t:
                cleaned.append(t)

        return self._dedupe_preserve_order(cleaned)

    def _pick_images(self, entity):
        images = []

        # nivel superior
        for key in ["image", "mainImage"]:
            val = entity.get(key)
            if val and isinstance(val, str):
                images.append(val)

        top_images = entity.get("images")
        if isinstance(top_images, list):
            images.extend([img for img in top_images if img])

        # properties
        props = entity.get("properties", {}) or {}

        for key in ["image", "mainImage", "candidateImage"]:
            val = props.get(key)
            if val and isinstance(val, str):
                images.append(val)

        additional = props.get("additionalImages")
        if isinstance(additional, list):
            images.extend([img for img in additional if img])

        # normalizar listas serializadas raras
        flat = []
        for img in images:
            s = self._clean_text(str(img))
            if not s:
                continue

            if s.startswith("[") and s.endswith("]"):
                inner = s[1:-1].strip()
                parts = [p.strip(" '\"") for p in inner.split(",") if p.strip(" '\"")]
                flat.extend(parts)
            elif "|" in s:
                flat.extend([x.strip() for x in s.split("|") if x.strip()])
            else:
                flat.append(s)

        flat = [
            x for x in flat
            if x.startswith("http://") or x.startswith("https://")
        ]

        return self._dedupe_preserve_order(flat)

    def _flatten_results(self, results):
        entities = []

        for item in results or []:
            if not item:
                continue

            if isinstance(item, dict) and "entities" in item:
                ents = item.get("entities") or []
                for e in ents:
                    if isinstance(e, dict):
                        entities.append(e)
            elif isinstance(item, dict):
                entities.append(item)

        return entities

    def _dedupe_entities(self, entities):
        grouped = {}

        for e in entities:
            name = self._clean_text(self._pick_name(e)).lower()
            if not name:
                continue

            if name not in grouped:
                grouped[name] = dict(e)
                continue

            current = grouped[name]

            # conservar score mayor
            if (e.get("score") or 0) > (current.get("score") or 0):
                current["score"] = e.get("score")

            # conservar texto más largo si falta o mejora
            for field in ["short_description", "long_description", "description", "address", "phone", "email", "sourceUrl", "url"]:
                old = self._clean_text(current.get(field, ""))
                new = self._clean_text(e.get(field, ""))
                if not old and new:
                    current[field] = new
                elif new and len(new) > len(old):
                    current[field] = new

            # merge properties
            old_props = current.get("properties", {}) or {}
            new_props = e.get("properties", {}) or {}
            for k, v in new_props.items():
                if k not in old_props or old_props[k] in (None, "", [], {}):
                    old_props[k] = v
            current["properties"] = old_props

            # merge related urls top-level
            old_related = self._normalize_related_urls(current.get("relatedUrls", []))
            new_related = self._normalize_related_urls(e.get("relatedUrls", []))
            current["relatedUrls"] = self._dedupe_preserve_order(old_related + new_related)

            # merge images top-level
            old_images = self._pick_images(current)
            new_images = self._pick_images(e)
            merged_images = self._dedupe_preserve_order(old_images + new_images)

            if merged_images:
                current["images"] = merged_images
                if not current.get("image"):
                    current["image"] = merged_images[0]
                if not current.get("mainImage"):
                    current["mainImage"] = merged_images[0]

            grouped[name] = current

        return list(grouped.values())

    # =========================================================
    # API pública
    # =========================================================

    def generate_markdown_report(self, results, output_file):
        entities = self._flatten_results(results)
        entities = self._dedupe_entities(entities)

        # ordenar por score desc y nombre
        entities = sorted(
            entities,
            key=lambda e: (
                -(e.get("score") or 0),
                self._pick_name(e).lower()
            )
        )

        lines = []
        lines.append("# Knowledge Graph")
        lines.append(f"Total de entidades: {len(entities)}")
        lines.append("")

        for entity in entities:
            name = self._pick_name(entity)
            types = self._pick_types(entity)
            score = entity.get("score", "")
            source_url = self._clean_text(entity.get("sourceUrl", ""))
            url = self._clean_text(entity.get("url", ""))
            address = self._clean_text(entity.get("address", ""))
            phone = self._clean_text(entity.get("phone", ""))
            email = self._clean_text(entity.get("email", ""))
            short_desc = self._clean_text(entity.get("short_description", ""))
            long_desc = self._clean_text(entity.get("long_description", ""))
            description = self._clean_text(entity.get("description", ""))
            related_urls = self._normalize_related_urls(entity.get("relatedUrls", []))
            images = self._pick_images(entity)

            lines.append(f"## {name}")
            lines.append("")

            if types:
                lines.append(f"**type:** {', '.join(types)}")

            if score != "":
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

            if short_desc:
                lines.append(f"**shortDescription:** {short_desc}")

            if long_desc:
                lines.append(f"**longDescription:** {long_desc}")

            if description and description != long_desc:
                lines.append(f"**description:** {description}")

            if images:
                lines.append("**images:**")
                lines.append("")
                for img in images[:3]:
                    lines.append(f"![{name}]({img})")
                    lines.append("")

            # campos de calidad si existen
            if entity.get("qualityScore") is not None:
                lines.append(f"**qualityScore:** {entity.get('qualityScore')}")

            if entity.get("qualityDecision"):
                lines.append(f"**qualityDecision:** {entity.get('qualityDecision')}")

            if entity.get("needsReview"):
                lines.append("**needsReview:** True")

            lines.append("")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))