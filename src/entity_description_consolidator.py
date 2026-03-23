class EntityDescriptionConsolidator:
    def _safe_text(self, value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _to_list(self, value):
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, (tuple, set)):
            return list(value)

        if isinstance(value, str):
            value = value.strip()
            return [value] if value else []

        return [value]

    def _merge_list_unique(self, current, candidate):
        current_list = self._to_list(current)
        candidate_list = self._to_list(candidate)

        seen = set()
        merged = []

        for item in current_list + candidate_list:
            if item is None:
                continue

            if isinstance(item, str):
                norm = item.strip()
                if not norm:
                    continue
                key = norm.lower()
                value = norm
            else:
                norm = str(item).strip()
                if not norm:
                    continue
                key = norm.lower()
                value = item

            if key not in seen:
                seen.add(key)
                merged.append(value)

        return merged

    def _merge_string_field(self, current, candidate):
        current = self._safe_text(current)
        candidate = self._safe_text(candidate)

        if not current and candidate:
            return candidate

        if candidate and len(candidate) > len(current):
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

    def _merge_properties(self, entity_name, current, candidate):
        current = current or {}
        candidate = candidate or {}
        merged = dict(current)

        for key, incoming in candidate.items():
            if incoming is None:
                continue

            if isinstance(incoming, str) and not incoming.strip():
                continue

            if key not in merged:
                merged[key] = incoming
                continue

            existing = merged[key]

            # Si alguno de los dos lados ya es lista/tupla/set, unificamos como lista única
            if isinstance(existing, (list, tuple, set)) or isinstance(incoming, (list, tuple, set)):
                merged[key] = self._merge_list_unique(existing, incoming)
                continue

            # string + string
            if isinstance(existing, str) and isinstance(incoming, str):
                existing_clean = existing.strip()
                incoming_clean = incoming.strip()

                if existing_clean.lower() == incoming_clean.lower():
                    merged[key] = existing_clean
                else:
                    merged[key] = self._merge_list_unique(existing_clean, incoming_clean)
                continue

            # dict + dict -> merge superficial conservador
            if isinstance(existing, dict) and isinstance(incoming, dict):
                new_dict = dict(existing)
                for sub_key, sub_value in incoming.items():
                    if sub_key not in new_dict or new_dict[sub_key] in (None, "", []):
                        new_dict[sub_key] = sub_value
                merged[key] = new_dict
                continue

            # Si son iguales, mantener el existente
            if existing == incoming:
                merged[key] = existing
                continue

            # Caso mixto genérico -> normalizar a lista única
            merged[key] = self._merge_list_unique(existing, incoming)

        return merged

    def _select_best(self, descriptions):
        if not descriptions:
            return ""
        return sorted(descriptions, key=len, reverse=True)[0]

    def consolidate(self, results):
        entity_map = {}

        for block in results:
            for e in block.get("entities", []):
                entity_name = e.get("entity_name") or e.get("entity") or ""
                if not entity_name:
                    continue

                key = entity_name.lower()

                if key not in entity_map:
                    entity_map[key] = {
                        "entity": e.get("entity", entity_name),
                        "entity_name": entity_name,
                        "class": e.get("class", ""),
                        "score": e.get("score", 0.0),
                        "verisimilitude_score": e.get("verisimilitude_score", e.get("score", 0.0)),
                        "properties": e.get("properties", {}),
                        "address": e.get("address", ""),
                        "phone": e.get("phone", ""),
                        "email": e.get("email", ""),
                        "coordinates": e.get("coordinates", {"lat": None, "lng": None}),
                        "short_descriptions": [],
                        "long_descriptions": [],
                        "wikidata_id": e.get("wikidata_id", ""),
                    }

                entity_map[key]["score"] = max(
                    entity_map[key]["score"],
                    e.get("score", 0.0)
                )

                entity_map[key]["verisimilitude_score"] = max(
                    entity_map[key]["verisimilitude_score"],
                    e.get("verisimilitude_score", e.get("score", 0.0))
                )

                entity_map[key]["properties"] = self._merge_properties(
                    entity_name,
                    entity_map[key].get("properties", {}),
                    e.get("properties", {})
                )

                entity_map[key]["address"] = self._merge_string_field(
                    entity_map[key].get("address", ""),
                    e.get("address", "")
                )

                entity_map[key]["phone"] = self._merge_string_field(
                    entity_map[key].get("phone", ""),
                    e.get("phone", "")
                )

                entity_map[key]["email"] = self._merge_string_field(
                    entity_map[key].get("email", ""),
                    e.get("email", "")
                )

                entity_map[key]["coordinates"] = self._merge_coordinates(
                    entity_map[key].get("coordinates", {"lat": None, "lng": None}),
                    e.get("coordinates", {"lat": None, "lng": None})
                )

                if not entity_map[key].get("wikidata_id") and e.get("wikidata_id"):
                    entity_map[key]["wikidata_id"] = e.get("wikidata_id")

                sd = e.get("short_description")
                ld = e.get("long_description")

                if sd:
                    entity_map[key]["short_descriptions"].append(sd)

                if ld:
                    entity_map[key]["long_descriptions"].append(ld)

        consolidated = []

        for e in entity_map.values():
            best_short = self._select_best(e["short_descriptions"])
            best_long = self._select_best(e["long_descriptions"])

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