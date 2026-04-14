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

    GENERIC_CLASSES = {
        "",
        "Thing",
        "Place",
        "Location",
        "TourismDestination",
        "TouristAttraction",
        "TouristAttractionSite",
        "Organization",
        "LocalBusiness",
        "Concept",
    }

    SPECIFIC_CLASS_PRIORITY = {
        "Alcazar": 100,
        "Cathedral": 98,
        "Basilica": 96,
        "Chapel": 95,
        "Church": 94,
        "Castle": 93,
        "ArcheologicalSite": 92,
        "Bullring": 91,
        "TownHall": 90,
        "Stadium": 89,
        "Square": 88,
        "Museum": 87,
        "ExhibitionHall": 86,
        "CultureCenter": 85,
        "EducationalCenter": 84,
        "SportsCenter": 83,
        "SportFacility": 82,
        "TransportInfrastructure": 81,
        "FoodEstablishment": 80,
        "AccommodationEstablishment": 79,
        "Accommodation": 78,
        "TourismService": 77,
        "PublicService": 76,
        "EventOrganisationCompany": 75,
        "Event": 70,
        "Person": 65,
        "TouristAttraction": 30,
        "TouristAttractionSite": 29,
        "TourismDestination": 20,
        "Place": 15,
        "Organization": 10,
        "LocalBusiness": 9,
        "Thing": 1,
        "Concept": 0,
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

    def _token_count(self, text):
        return len(self._canonical_key(text).split())

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
        if not candidate:
            return current

        # preferimos el texto más largo y más informativo
        if len(candidate) > len(current):
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

            if key in {"name", "title", "label"} and self._is_portal_text(value):
                return None

            if key in {"telephone", "phone"}:
                return self._clean_phone(value) or None

            if key == "email":
                return self._clean_email(value) or None

            if key in {"image", "mainImage"}:
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

            if isinstance(merged[key], str) and isinstance(value, str):
                if len(value) > len(merged[key]):
                    merged[key] = value

        return merged

    def _select_best_description(self, descriptions):
        descriptions = [self._safe_text(d) for d in descriptions if self._safe_text(d)]
        if not descriptions:
            return ""

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

        if name in {"tablaos flamencos", "academias de flamenco", "cante jondo"}:
            return "Concept"

        if name in {"altozano de triana", "sevilla", "triana"}:
            return "Place"

        if entity_class in {"LocalBusiness", "Location"}:
            return "Thing"

        return entity_class or "Thing"

    def _class_priority(self, cls):
        cls = self._safe_text(cls)
        return self.SPECIFIC_CLASS_PRIORITY.get(cls, 0)

    def _choose_best_class(self, current_class, candidate_class, entity_name=""):
        current_class = self._normalize_class(entity_name, current_class)
        candidate_class = self._normalize_class(entity_name, candidate_class)

        if not current_class:
            return candidate_class or "Thing"
        if not candidate_class:
            return current_class

        if self._class_priority(candidate_class) > self._class_priority(current_class):
            return candidate_class

        return current_class

    def _choose_best_name(self, current_name, candidate_name):
        current_name = self._normalize_name(current_name)
        candidate_name = self._normalize_name(candidate_name)

        if not current_name and candidate_name:
            return candidate_name
        if not candidate_name:
            return current_name

        current_key = self._canonical_key(current_name)
        candidate_key = self._canonical_key(candidate_name)

        if current_key == candidate_key:
            # si son equivalentes, preferimos la variante más larga
            if len(candidate_name) > len(current_name):
                return candidate_name
            return current_name

        # si uno contiene al otro, preferimos el más específico/largo
        if current_key and candidate_key:
            if current_key in candidate_key and len(candidate_name) > len(current_name):
                return candidate_name
            if candidate_key in current_key and len(current_name) >= len(candidate_name):
                return current_name

        # por defecto, preferimos el más largo
        if len(candidate_name) > len(current_name):
            return candidate_name
        return current_name

    def _choose_best_entity_field(self, current_value, candidate_value, best_name):
        current_value = self._normalize_name(current_value)
        candidate_value = self._normalize_name(candidate_value)

        if not current_value:
            return candidate_value or best_name
        if not candidate_value:
            return current_value or best_name

        current_key = self._canonical_key(current_value)
        candidate_key = self._canonical_key(candidate_value)
        best_key = self._canonical_key(best_name)

        if candidate_key == best_key and current_key != best_key:
            return candidate_value
        if current_key == best_key:
            return current_value

        if len(candidate_value) > len(current_value):
            return candidate_value
        return current_value

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
                        "name": e.get("name", entity_name),
                        "label": e.get("label", entity_name),
                        "class": self._normalize_class(entity_name, e.get("class", "")),
                        "type": e.get("type"),
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

                # preferimos el mejor nombre observado
                entity_map[key]["entity_name"] = self._choose_best_name(
                    entity_map[key].get("entity_name", ""),
                    entity_name,
                )

                best_name = entity_map[key]["entity_name"]

                entity_map[key]["entity"] = self._choose_best_entity_field(
                    entity_map[key].get("entity", ""),
                    e.get("entity", entity_name),
                    best_name,
                )
                entity_map[key]["name"] = self._choose_best_entity_field(
                    entity_map[key].get("name", ""),
                    e.get("name", entity_name),
                    best_name,
                )
                entity_map[key]["label"] = self._choose_best_entity_field(
                    entity_map[key].get("label", ""),
                    e.get("label", entity_name),
                    best_name,
                )

                entity_map[key]["score"] = max(
                    entity_map[key]["score"],
                    e.get("score", 0.0),
                )

                entity_map[key]["verisimilitude_score"] = max(
                    entity_map[key]["verisimilitude_score"],
                    e.get("verisimilitude_score", e.get("score", 0.0)),
                )

                current_class = entity_map[key]["class"]
                new_class = self._normalize_class(best_name, e.get("class", ""))

                entity_map[key]["class"] = self._choose_best_class(
                    current_class,
                    new_class,
                    entity_name=best_name,
                )

                if e.get("type") and not entity_map[key].get("type"):
                    entity_map[key]["type"] = e.get("type")

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

            best_name = self._normalize_name(e["entity_name"])

            item = {
                "entity": self._choose_best_entity_field(e.get("entity", ""), best_name, best_name),
                "entity_name": best_name,
                "name": self._choose_best_entity_field(e.get("name", ""), best_name, best_name),
                "label": self._choose_best_entity_field(e.get("label", ""), best_name, best_name),
                "class": e["class"],
                "type": e.get("type"),
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