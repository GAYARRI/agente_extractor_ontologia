# src/export/json_exporter.py
import json
import re
from collections import Counter
from pathlib import Path

from entity_processing.scoring import apply_entity_scores
from entity_processing.text_cleaning import clean_text


class JSONExporter:
    def __init__(self):
        self.max_images = 3

    def _normalize_space(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    def _clean_text(self, value: str) -> str:
        v = self._normalize_space(clean_text(value))
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
            "visita_burgos_fondo",
            "burgos_fondo",
            "_fondo",
            "fondo.png",
            "desliza.png",
            "whatsapp",
            "facebook",
            "instagram",
            "youtube",
        ]
        if any(b in low for b in bad_patterns):
            return False
        if ".svg" in low:
            return False
        return True

    def _image_quality(self, entity: dict, image: str) -> tuple[str, str]:
        low = self._clean_text(image).lower()
        if not low:
            return "missing", ""
        if "desliza.png" in low:
            return "generic", "generic_slider_placeholder"
        if any(x in low for x in ("whatsapp", "facebook", "instagram", "youtube", "share", "social")):
            return "rejected", "social_or_share_asset"

        evidence = self._extract_image_records(entity, "imageEvidence")
        if any(item.get("src") == image and item.get("accepted") is True for item in evidence):
            return "specific", ""

        weak_tokens = {
            "burgos", "museo", "municipal", "catedral", "iglesia", "palacio",
            "monasterio", "convento", "santa", "maria", "real", "casa",
            "parque", "puente", "hotel", "datos", "api",
        }
        name_tokens = [
            token
            for token in re.split(r"[^\w]+", self._canonical_key(self._choose_name(entity)))
            if len(token) > 3 and token not in weak_tokens
        ]
        if name_tokens and any(token in low for token in name_tokens):
            return "specific", ""

        return "unverified", "no_entity_image_evidence"

    def _is_exportable_entity(self, entity: dict) -> bool:
        name = self._canonical_key(self._choose_name(entity))
        if not name:
            return False
        if name.endswith((" de", " del", " la", " el", " los", " las", " y")):
            return False
        if name.startswith(("de ", "del ", "y ")):
            return False
        if any(token in name for token in ("datos api", "continuamos", "cruzando")):
            return False
        if " madrid" in f" {name} ":
            return False
        return True

    def _to_float(self, value):
        try:
            if value in (None, ""):
                return None
            return float(value)
        except Exception:
            return None

    def _is_burgos_source(self, entity: dict) -> bool:
        source = " ".join(
            self._clean_text(entity.get(key))
            for key in ("sourceUrl", "url")
        ).lower()
        return "visitaburgosciudad.es" in source

    def _coords_in_burgos_scope(self, lat, lng) -> bool:
        lat = self._to_float(lat)
        lng = self._to_float(lng)
        if lat is None or lng is None:
            return False
        return 41.2 <= lat <= 43.4 and -4.6 <= lng <= -2.5

    def _canonical_key(self, text: str) -> str:
        value = self._clean_text(text).lower()
        value = re.sub(r"[^\wáéíóúñü]+", " ", value, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", value).strip()

    def _is_coordinate_name_safe(self, entity: dict) -> bool:
        key = self._canonical_key(self._choose_name(entity))
        if not key:
            return False
        tokens = [token for token in key.split() if token]
        if len(tokens) < 2:
            return False
        trailing_fragments = {
            "de", "del", "la", "el", "los", "las", "y", "en", "para", "por",
            "paseo", "ruta", "rutas", "parque", "plaza", "mercado", "museo",
            "palacio", "iglesia", "catedral", "convento", "albergues",
            "apartamentos", "alojamientos", "eventos",
        }
        if tokens[-1] in trailing_fragments:
            return False
        generic_exact = {
            "parque natural",
            "plaza huerto",
            "rutas urbanas",
            "eventos en burgos",
            "albergues",
            "alojamientos en burgos",
            "alojamientos hoteleros",
            "apartamentos turisticos",
            "centro de aves",
            "cordillera cantabrica",
            "sistema iberico",
            "orientacion parque",
            "espolon parque",
            "quinta parque",
            "mercado mayor",
            "muralla la ciudad",
            "iglesia en burgos",
        }
        return key not in generic_exact

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
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if inner:
                parts = [p.strip(" '\"") for p in inner.split(",") if p.strip(" '\"")]
                flat.extend(parts)
            return flat
        if "|" in value:
            flat.extend([x.strip() for x in value.split("|") if x.strip()])
            return flat
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
        return cleaned[:self.max_images]

    def _extract_candidate_images(self, entity):
        props = entity.get("properties", {}) or {}
        if not isinstance(props, dict):
            props = {}
        candidates = [
            entity.get("candidateImage", ""),
            entity.get("candidateImages", []),
            props.get("candidateImage", ""),
            props.get("candidateImages", []),
        ]
        flat = []
        for c in candidates:
            flat.extend(self._flatten_maybe_serialized_list(c))
        cleaned = []
        seen = set()
        for img in flat:
            img = self._clean_text(img)
            if not img or not img.startswith(("http://", "https://")):
                continue
            if img in seen:
                continue
            seen.add(img)
            cleaned.append(img)
        return cleaned[:10]

    def _extract_image_records(self, entity, field):
        props = entity.get("properties", {}) or {}
        if not isinstance(props, dict):
            props = {}
        raw = entity.get(field) or props.get(field) or []
        if not isinstance(raw, list):
            return []
        out = []
        for item in raw[:20]:
            if isinstance(item, dict):
                src = self._clean_text(item.get("src"))
                if not src:
                    continue
                out.append(
                    {
                        "src": src,
                        "reason": self._clean_text(item.get("reason") or item.get("rejectionReason")),
                        "source": self._clean_text(item.get("source")),
                        "score": item.get("score"),
                        "entityScore": item.get("entityScore"),
                        "contextScore": item.get("contextScore"),
                        "accepted": item.get("accepted"),
                    }
                )
            else:
                src = self._clean_text(item)
                if src:
                    out.append({"src": src})
        return out

    def _pick_image_roles(self, entity, images):
        props = entity.get("properties", {}) or {}

        def _valid(value):
            value = self._clean_text(value)
            return value if self._is_valid_image_url(value) else ""

        explicit_image = _valid(entity.get("image") or props.get("image"))
        explicit_main = _valid(entity.get("mainImage") or props.get("mainImage"))

        image = explicit_image or (images[0] if images else "")
        main_image = explicit_main or ""

        if not main_image:
            if len(images) > 1 and images[1] != image:
                main_image = images[1]
            else:
                main_image = image
        elif main_image == image and len(images) > 1 and images[1] != image:
            main_image = images[1]

        return image, main_image

    def _pick_additional_images(self, images, image, main_image):
        extras = []
        seen = set()

        for img in images:
            if img == image or img == main_image:
                continue
            if img in seen:
                continue
            seen.add(img)
            extras.append(img)

        return extras[:1]

    def _extract_types(self, entity):
        types = []
        types.extend(self._as_list(entity.get("types")))
        types.extend(self._as_list(entity.get("type")))
        types.extend(self._as_list(entity.get("class")))
        props = entity.get("properties", {}) or {}
        if isinstance(props, dict):
            types.extend(self._as_list(props.get("type")))
        cleaned = [self._normalize_space(t) for t in types if t]
        return self._dedupe(cleaned)

    def _extract_raw_types(self, entity):
        raw_types = []
        raw_types.extend(self._as_list(entity.get("types_raw")))
        raw_types.extend(self._as_list(entity.get("class_raw")))
        cleaned = [self._normalize_space(t) for t in raw_types if t]
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
        lat = self._to_float(lat)
        lng = self._to_float(lng)
        if lat is not None and not (-90 <= lat <= 90):
            lat = None
        if lng is not None and not (-180 <= lng <= 180):
            lng = None
        if not self._is_coordinate_name_safe(entity):
            lat = None
            lng = None
        if self._is_burgos_source(entity) and not self._coords_in_burgos_scope(lat, lng):
            lat = None
            lng = None
        return {
            "lat": lat,
            "lng": lng,
        }

    def _pick_page_url(self, entity: dict) -> str:
        return self._clean_text(entity.get("url") or entity.get("sourceUrl"))

    def _pick_primary_type(self, entity: dict) -> str:
        final_class = self._clean_text(entity.get("class"))
        if final_class:
            return final_class
        types = self._extract_types(entity)
        return types[0] if types else "Unknown"

    def _public_entity_payload(self, entity: dict) -> dict:
        return {
            "entityId": entity.get("entityId"),
            "name": entity.get("name"),
            "class": entity.get("class"),
            "classUri": entity.get("classUri"),
            "classParents": entity.get("classParents", []),
            "classAncestors": entity.get("classAncestors", []),
            "types": entity.get("types", []),
            "typesRaw": entity.get("typesRaw", []),
            "ontologyMatch": entity.get("ontologyMatch"),
            "ontologyRejectionReason": entity.get("ontologyRejectionReason"),
            "sourceOntology": entity.get("sourceOntology"),
            "score": entity.get("score"),
            "sourceUrl": entity.get("sourceUrl"),
            "url": entity.get("url"),
            "pageStructure": entity.get("pageStructure"),
            "pageRole": entity.get("pageRole"),
            "mentionRole": entity.get("mentionRole"),
            "mentionRelation": entity.get("mentionRelation"),
            "relatedUrls": entity.get("relatedUrls", []),
            "address": entity.get("address"),
            "phone": entity.get("phone"),
            "email": entity.get("email"),
            "coordinates": entity.get("coordinates", {"lat": None, "lng": None}),
            "shortDescription": entity.get("shortDescription"),
            "longDescription": entity.get("longDescription"),
            "description": entity.get("description"),
            "image": entity.get("image"),
            "mainImage": entity.get("mainImage"),
            "images": entity.get("images", []),
            "additionalImages": entity.get("additionalImages", []),
            "wikidataId": entity.get("wikidataId"),
        }

    def _nested_entity_node(self, entity: dict) -> dict:
        node = self._public_entity_payload(entity)
        node["relationshipType"] = entity.get("relationshipType")
        node["children"] = []
        return node

    def build_hierarchical_export(self, entities: list, pages=None) -> dict:
        normalized_entities = [entity for entity in entities or [] if isinstance(entity, dict)]
        page_urls = self._normalize_pages(pages)
        grouped: dict[str, list] = {}

        for entity in normalized_entities:
            page_url = self._pick_page_url(entity) or "UNKNOWN_PAGE"
            grouped.setdefault(page_url, []).append(entity)

        for page_url in page_urls:
            grouped.setdefault(page_url, [])

        page_groups = []
        for page_url in sorted(grouped.keys(), key=lambda value: value.lower()):
            page_entities = grouped.get(page_url, [])
            id_map = {}
            child_map = {}
            roots = []
            standalone = []
            page_structure_value = self._clean_text(page_entities[0].get("pageStructure")) if page_entities else ""

            for entity in page_entities:
                entity_id = self._clean_text(entity.get("entityId"))
                if entity_id:
                    id_map[entity_id] = entity
                parent_id = self._clean_text(entity.get("parentEntityId"))
                if parent_id:
                    child_map.setdefault(parent_id, []).append(entity)

            used_root_ids = set()
            for entity in page_entities:
                entity_id = self._clean_text(entity.get("entityId"))
                page_role = self._clean_text(entity.get("pageRole")).lower()
                parent_id = self._clean_text(entity.get("parentEntityId"))
                if parent_id:
                    continue
                if page_role in {"primary", "standalone"} or entity_id in child_map or not entity_id:
                    if entity_id and entity_id in used_root_ids:
                        continue
                    roots.append(entity)
                    if entity_id:
                        used_root_ids.add(entity_id)

            if page_structure_value == "hierarchical":
                primary_roots = [
                    entity
                    for entity in roots
                    if self._clean_text(entity.get("pageRole")).lower() == "primary"
                ]
                if primary_roots:
                    standalone.extend(entity for entity in roots if entity not in primary_roots)
                    roots = primary_roots

            for entity in page_entities:
                entity_id = self._clean_text(entity.get("entityId"))
                parent_id = self._clean_text(entity.get("parentEntityId"))
                if parent_id:
                    continue
                if entity not in roots:
                    standalone.append(entity)
                elif not entity_id:
                    standalone.append(entity)

            def build_node(entity: dict) -> dict:
                node = self._nested_entity_node(entity)
                entity_id = self._clean_text(entity.get("entityId"))
                children = child_map.get(entity_id, []) if entity_id else []
                node["children"] = [build_node(child) for child in children]
                return node

            root_nodes = [build_node(entity) for entity in roots]
            standalone_nodes = []
            seen_standalone = set()
            for entity in standalone:
                key = self._clean_text(entity.get("entityId")) or self._choose_name(entity)
                if not key or key in seen_standalone:
                    continue
                seen_standalone.add(key)
                standalone_nodes.append(self._nested_entity_node(entity))

            page_groups.append(
                {
                    "url": page_url,
                    "pageStructure": page_structure_value,
                    "entityCount": len(page_entities),
                    "rootEntities": root_nodes,
                    "standaloneEntities": standalone_nodes,
                }
            )

        return {
            "totalPages": len(page_groups),
            "totalEntities": len(normalized_entities),
            "pages": page_groups,
        }

    def _normalize_pages(self, pages) -> list:
        normalized = []
        for item in pages or []:
            if isinstance(item, (list, tuple)) and item:
                page_url = self._clean_text(item[0])
            else:
                page_url = self._clean_text(item)
            if page_url:
                normalized.append(page_url)
        return self._dedupe(normalized)

    def build_page_summary(self, entities: list, pages=None) -> dict:
        all_pages = self._normalize_pages(pages)
        page_totals = Counter({page_url: 0 for page_url in all_pages})
        page_type_totals = {page_url: Counter() for page_url in all_pages}

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            page_url = self._pick_page_url(entity) or "UNKNOWN_PAGE"
            entity_type = self._pick_primary_type(entity)

            page_totals[page_url] += 1
            if page_url not in page_type_totals:
                page_type_totals[page_url] = Counter()
            page_type_totals[page_url][entity_type] += 1

        pages_by_entity_count = Counter(page_totals.values())
        pages_without_entities = pages_by_entity_count.get(0, 0)

        pages = []
        for page_url, total in sorted(
            page_totals.items(),
            key=lambda item: (-item[1], item[0].lower())
        ):
            type_counts = dict(
                sorted(
                    page_type_totals[page_url].items(),
                    key=lambda item: (-item[1], item[0].lower())
                )
            )
            pages.append(
                {
                    "url": page_url,
                    "entityCount": total,
                    "entityTypeCounts": type_counts,
                }
            )

        return {
            "totalPages": len(page_totals),
            "totalEntities": sum(page_totals.values()),
            "pagesWithoutEntities": pages_without_entities,
            "pagesWithEntities": len(page_totals) - pages_without_entities,
            "pagesByEntityCount": {
                str(entity_count): page_count
                for entity_count, page_count in sorted(pages_by_entity_count.items())
            },
            "pages": pages,
        }

    def entity_to_dict(self, entity: dict) -> dict:
        coords = self._extract_coordinates(entity)
        images = self._extract_images(entity)
        primary_image, main_image = self._pick_image_roles(entity, images)
        additional_images = self._pick_additional_images(images, primary_image, main_image)
        wikidata_id = self._clean_text(entity.get("wikidata_id") or entity.get("wikidataId"))
        final_class = self._clean_text(entity.get("class"))
        entity_id = self._clean_text(entity.get("entityId"))
        page_structure = self._clean_text(entity.get("pageStructure"))
        page_role = self._clean_text(entity.get("pageRole"))
        parent_entity_id = self._clean_text(entity.get("parentEntityId"))
        relationship_type = self._clean_text(entity.get("relationshipType"))
        mention_role = self._clean_text(entity.get("mentionRole"))
        mention_relation = self._clean_text(entity.get("mentionRelation"))
        image_quality, image_rejection_reason = self._image_quality(entity, main_image or primary_image)
        props = entity.get("properties", {}) or {}
        if not isinstance(props, dict):
            props = {}
        geo_source = self._clean_text(entity.get("geoSource") or props.get("geo_source"))
        geo_confidence = self._clean_text(entity.get("geoConfidence") or props.get("geo_confidence"))
        if coords.get("lat") is not None and coords.get("lng") is not None and not geo_source:
            geo_source = "existing_coordinates"
            geo_confidence = geo_confidence or "existing_unannotated"
        if image_quality in {"generic", "rejected", "unverified"}:
            primary_image = ""
            main_image = ""
            additional_images = []
            image_rejection_reason = image_rejection_reason or "not_verified_for_entity"
            image_quality = "missing"

        out = {
            "entityId": entity_id,
            "name": self._choose_name(entity),
            "class": final_class or None,
            "classUri": self._clean_text(entity.get("classUri")),
            "classParents": self._dedupe(self._as_list(entity.get("classParents"))),
            "classAncestors": self._dedupe(self._as_list(entity.get("classAncestors"))),
            "types": self._extract_types(entity),
            "typesRaw": self._extract_raw_types(entity),
            "ontologyMatch": bool(entity.get("ontologyMatch")),
            "ontologyRejectionReason": entity.get("ontologyRejectionReason"),
            "sourceOntology": self._clean_text(entity.get("sourceOntology")),
            "score": entity.get("score"),
            "extractionScore": entity.get("extractionScore"),
            "ontologyScore": entity.get("ontologyScore"),
            "qualityScore": entity.get("qualityScore"),
            "finalScore": entity.get("finalScore"),
            "qualityDecision": self._clean_text(entity.get("qualityDecision")),
            "qualityReasons": self._dedupe(self._as_list(entity.get("qualityReasons"))),
            "sourceUrl": self._clean_text(entity.get("sourceUrl")),
            "url": self._clean_text(entity.get("url")),
            "pageStructure": page_structure,
            "pageRole": page_role,
            "parentEntityId": parent_entity_id or None,
            "relationshipType": relationship_type or None,
            "mentionRole": mention_role,
            "mentionRelation": mention_relation or None,
            "relatedUrls": self._extract_related_urls(entity),
            "sourceUrls": self._dedupe(self._as_list(entity.get("sourceUrls"))),
            "address": self._clean_text(entity.get("address")),
            "phone": self._clean_text(entity.get("phone")),
            "email": self._clean_text(entity.get("email")),
            "coordinates": {
                "lat": coords.get("lat"),
                "lng": coords.get("lng"),
            },
            "geoSource": geo_source,
            "geoConfidence": geo_confidence,
            "geoQuery": self._clean_text(entity.get("geoQuery") or props.get("geo_query")),
            "geoRejectedReason": self._clean_text(entity.get("geoRejectedReason") or props.get("geo_rejected_reason")),
            "shortDescription": self._clean_text(entity.get("short_description") or entity.get("shortDescription")),
            "longDescription": self._clean_text(entity.get("long_description") or entity.get("longDescription")),
            "description": self._clean_text(entity.get("description")),
            "image": primary_image,
            "mainImage": main_image,
            "imageQuality": image_quality,
            "imageRejectionReason": image_rejection_reason,
            "candidateImages": self._extract_candidate_images(entity),
            "rejectedImages": self._extract_image_records(entity, "rejectedImages"),
            "imageEvidence": self._extract_image_records(entity, "imageEvidence"),
            "images": additional_images,
            "additionalImages": additional_images,
            "wikidataId": wikidata_id,
        }
        return apply_entity_scores(out)

    def export(self, entities: list, output_path="entities.json", pages=None):
        data = [
            self.entity_to_dict(e)
            for e in entities
            if isinstance(e, dict) and self._is_exportable_entity(e)
        ]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        output_file = Path(output_path)
        summary_path = output_file.with_name(f"{output_file.stem}_page_counts.json")
        hierarchical_path = output_file.with_name(f"{output_file.stem}_hierarchical.json")
        base_hierarchical_path = Path("entities_hierarchical.json")
        summary = self.build_page_summary(data, pages=pages)
        hierarchical = self.build_hierarchical_export(data, pages=pages)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        with open(hierarchical_path, "w", encoding="utf-8") as f:
            json.dump(hierarchical, f, ensure_ascii=False, indent=2)
        if output_file.name == "entities.json" and hierarchical_path.resolve() != base_hierarchical_path.resolve():
            with open(base_hierarchical_path, "w", encoding="utf-8") as f:
                json.dump(hierarchical, f, ensure_ascii=False, indent=2)

        return data
