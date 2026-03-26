import re
import unicodedata


class EntityDescriptionConsolidator:
    PORTAL_EMAIL_BLOCKLIST = {
        "visitasevilla@sevillacityoffice.es",
    }

    PORTAL_TEXT_BLOCKLIST = {
        "te queda mucho por descubrir:",
        "visita sevilla",
        "el flamenco - visita sevilla",
    }

    def _safe_text(self, value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _strip_accents(self, text):
        return "".join(
            ch for ch in unicodedata.normalize("NFKD", text)
            if not unicodedata.combining(ch)
        )

    def _normalize_name(self, text):
        text = self._safe_text(text)
        text = re.sub(r"^\d+[_\-\.\)]\s*", "", text)
        text = re.sub(r"\s+", " ", text)
        text = text.strip(" .,;:!¡?¿\"'“”‘’()[]{}")
        return text.strip()

    def _canonical_key(self, text):
        text = self._normalize_name(text).lower()
        text = self._strip_accents(text)
        return text

    def _is_portal_text(self, value):
        value_n = self._canonical_key(value)
        if not value_n:
            return True
        return value_n in {
            self._canonical_key(x) for x in self.PORTAL_TEXT_BLOCKLIST
        }

    def _clean_string_field(self, value):
        value = self._safe_text(value)
        if not value:
            return ""
        if self._is_portal_text(value):
            return ""
        return value

    def _clean_email(self, value):
        value = self._safe_text(value).lower()
        if not value:
            return ""
        if value in self.PORTAL_EMAIL_BLOCKLIST:
            return ""
        return value

    def _clean_phone(self, value):
        value = self._safe_text(value)
        if not value:
            return ""
        digits = re.sub(r"\D", "", value)
        if len(digits) < 9:
            return ""
        return value

    def _merge_string_field(self, current, candidate):
        current = self._clean_string_field(current)
        candidate = self._clean_string_field(candidate)

        if not current and candidate:
            return candidate
        if candidate and len(candidate) > len(current):
            return candidate
        return current

    def _merge_email(self, current, candidate):
        current = self._clean_email(current)
        candidate = self._clean_email(candidate)

        if not current and candidate:
            return candidate
        return current

    def _merge_phone(self, current, candidate):
        current = self._clean_phone(current)
        candidate = self._clean_phone(candidate)

        if not current and candidate:
            return candidate
        return current

    def _merge_coordinates(self, current, candidate):
        current = current or {"lat": None, "lng": None}
        candidate = candidate or {"lat": None, "lng": None}

        if current.get("lat") is None and candidate.get("lat") is not None:
            current["lat"] = candidate.get("lat")
        if current.get("lng") is None and candidate.get("lng") is not None:
            current["lng"] = candidate.get("lng")
        return current

    def _clean_property_value(self, key, value):
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None

            if key in {"name", "title"} and self._is_portal_text(value):
                return None

            if key in {"telephone", "phone"}:
                return self._clean_phone(value) or None

            if key == "email":
                return self._clean_email(value) or None

            if key in {"image", "mainImage"}:
                # evita conservar imágenes genéricas si luego no tienes match mejor
                if "el-flamenco-bloque-2.jpg" in value:
                    return None

            return value

        if isinstance(value, list):
            cleaned = []
            seen = set()
            for item in value:
                item_clean = self._clean_property_value(key, item)
                if item_clean is None:
                    continue
                norm = str(item_clean).strip().lower()
                if norm not in seen:
                    seen.add(norm)
                    cleaned.append(item_clean)
            return cleaned or None

        return value

    def _merge_properties(self, current, candidate):
        current = current or {}
        candidate = candidate or {}
        merged = dict(current)

        for key, value in candidate.items():
            value = self._clean_property_value(key, value)
            if value is None:
                continue

            if key not in merged or merged[key] in [None, "", []]:
                merged[key] = value
                continue

            if isinstance(merged[key], list) and isinstance(value, list):
                seen = set()
                merged_list = []
                for item in merged[key] + value:
                    norm = str(item).strip().lower()
                    if norm and norm not in seen:
                        seen.add(norm)
                        merged_list.append(item)
                merged[key] = merged_list
                continue

            # para strings no sobreescribimos con datos peores
            if isinstance(merged[key], str) and isinstance(value, str):
                if len(value) > len(merged[key]):
                    merged[key] = value

        return merged

    def _select_best_description(self, descriptions):
        descriptions = [self._safe_text(d) for d in descriptions if self._safe_text(d)]
        if not descriptions:
            return ""

        # penaliza descripciones demasiado genéricas
        bad_fragments = [
            "te queda mucho por descubrir",
            "visita sevilla",
            "descubre la muy famosa",
        ]

        scored = []
        for d in descriptions:
            penalty = 0
            dl = d.lower()
            if any(b in dl for b in bad_fragments):
                penalty -= 100
            scored.append((len(d) + penalty, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _normalize_class(self, entity_name, entity_class):
        name = self._canonical_key(entity_name)
        entity_class = self._safe_text(entity_class)

        if name in {"manolo caracol", "nina de los peines", "la nina de los peines", "pastora pavon"}:
            return "Person"

        if name in {"tablaos flamencos", "academias de flamenco", "cante jondo", "sevilla academias"}:
            return "Concept"

        if name in {"altozano de triana", "sevilla", "triana"}:
            return "Place"

        if entity_class in {"LocalBusiness", "Location"}:
            return "Thing"

        return entity_class or "Thing"

    def consolidate(self, results):
        entity_map = {}

        for block in results:
            for e in block.get("entities", []):
                entity_name = self._normalize_name(
                    e.get("entity_name") or e.get("entity") or e.get("name") or ""
                )
                if not entity_name:
                    continue

                key = self._canonical_key(entity_name)

                if key not in entity_map:
                    entity_map[key] = {
                        "entity": e.get("entity", entity_name),
                        "entity_name": entity_name,
                        "class": self._normalize_class(entity_name, e.get("class", "")),
                        "score": e.get("score", 0.0),
                        "verisimilitude_score": e.get("verisimilitude_score", e.get("score", 0.0)),
                        "properties": self._merge_properties({}, e.get("properties", {})),
                        "address": self._clean_string_field(e.get("address", "")),
                        "phone": self._clean_phone(e.get("phone", "")),
                        "email": self._clean_email(e.get("email", "")),
                        "coordinates": e.get("coordinates", {"lat": None, "lng": None}) or {"lat": None, "lng": None},
                        "short_descriptions": [],
                        "long_descriptions": [],
                        "wikidata_id": e.get("wikidata_id", ""),
                    }

                entity_map[key]["score"] = max(
                    entity_map[key]["score"],
                    e.get("score", 0.0),
                )

                entity_map[key]["verisimilitude_score"] = max(
                    entity_map[key]["verisimilitude_score"],
                    e.get("verisimilitude_score", e.get("score", 0.0)),
                )

                # normaliza clase si llega algo más específico
                current_class = entity_map[key]["class"]
                new_class = self._normalize_class(entity_name, e.get("class", ""))
                if current_class in {"Thing", ""} and new_class not in {"Thing", ""}:
                    entity_map[key]["class"] = new_class

                entity_map[key]["properties"] = self._merge_properties(
                    entity_map[key].get("properties", {}),
                    e.get("properties", {}),
                )

                entity_map[key]["address"] = self._merge_string_field(
                    entity_map[key].get("address", ""),
                    e.get("address", ""),
                )
                entity_map[key]["phone"] = self._merge_phone(
                    entity_map[key].get("phone", ""),
                    e.get("phone", ""),
                )
                entity_map[key]["email"] = self._merge_email(
                    entity_map[key].get("email", ""),
                    e.get("email", ""),
                )
                entity_map[key]["coordinates"] = self._merge_coordinates(
                    entity_map[key].get("coordinates", {"lat": None, "lng": None}),
                    e.get("coordinates", {"lat": None, "lng": None}),
                )

                if not entity_map[key].get("wikidata_id") and e.get("wikidata_id"):
                    entity_map[key]["wikidata_id"] = e.get("wikidata_id")

                sd = self._safe_text(e.get("short_description"))
                ld = self._safe_text(e.get("long_description"))

                if sd:
                    entity_map[key]["short_descriptions"].append(sd)
                if ld:
                    entity_map[key]["long_descriptions"].append(ld)

        consolidated = []

        for e in entity_map.values():
            best_short = self._select_best_description(e["short_descriptions"])
            best_long = self._select_best_description(e["long_descriptions"])

            item = {
                "entity": e["entity"],
                "entity_name": e["entity_name"],
                "class": e["class"],
                "score": e["score"],
                "verisimilitude_score": e["verisimilitude_score"],
                "properties": e["properties"],
                "short_description": best_short,
                "long_description": best_long,
                "address": e["address"],
                "phone": e["phone"],
                "email": e["email"],
                "coordinates": e["coordinates"],
            }

            if e.get("wikidata_id"):
                item["wikidata_id"] = e["wikidata_id"]

            consolidated.append(item)

        consolidated.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return consolidated