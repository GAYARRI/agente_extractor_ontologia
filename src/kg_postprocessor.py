from __future__ import annotations

import re
import unicodedata

from src.entity_quality_scorer import EntityQualityScorer


class KGPostProcessor:
    def __init__(self):
        self.quality_scorer = EntityQualityScorer()

        self.hard_bad_suffixes = {
            " leer",
        }

        self.hard_bad_exact = {
            "ruta",
            "mercado",
            "evento",
            "servicios",
        }

        self.bad_address_fragments = [
            "leer más",
            "leer mas",
            "mostrar más",
            "mostrar mas",
            "alcalde marques de contadero",
            "de toros histórica que tuvo sevilla",
            "de toros historica que tuvo sevilla",
        ]

        self.global_phone_values = {
            "34) 955 471 232",
            "+34) 955 471 232",
            "+34 955 471 232",
            "955 471 232",
        }

        self.global_email_values = {
            "visitasevilla@sevillacityoffice.es",
        }

        # Clases alineadas con tu pipeline/ranker/taxonomía actual
        self.allowed_types = {
            "Thing",
            "Place",
            "Organization",
            "Service",
            "Concept",
            "Event",
            "TouristAttraction",
            "Monument",
            "Museum",
            "Castle",
            "Alcazar",
            "Basilica",
            "Cathedral",
            "Church",
            "Chapel",
            "ArcheologicalSite",
            "HistoricalOrCulturalResource",
            "Square",
            "TownHall",
            "BullRing",
            "SportsCenter",
            "CultureCenter",
            "ExhibitionHall",
            "EducationalCenter",
            "DestinationExperience",
            "RetailAndFashion",
            "TourismService",
            "Accommodation",
            "AccommodationEstablishment",
            "FoodEstablishment",
            "TransportInfrastructure",
            "EventOrganisationCompany",
            "EventAttendanceFacility",
            "PublicService",
            "Stadium",
        }

        self.generic_types = {
            "Thing",
            "Place",
            "Organization",
            "Service",
            "Concept",
            "Accommodation",
        }

    # =========================================================
    # Helpers
    # =========================================================

    def _normalize(self, text: str) -> str:
        text = text or ""
        text = text.strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _first_nonempty(self, value):
        if isinstance(value, list):
            for v in value:
                s = str(v).strip()
                if s:
                    return s
            return ""
        if value is None:
            return ""
        return str(value).strip()

    def _clean_text(self, text):
        if text is None:
            return ""

        if isinstance(text, list):
            text = " | ".join(str(x).strip() for x in text if x is not None and str(x).strip())
        elif isinstance(text, tuple):
            text = " | ".join(str(x).strip() for x in text if x is not None and str(x).strip())
        else:
            text = str(text).strip()

        return text

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
        return self._dedupe(items)

    def _entity_name(self, entity: dict) -> str:
        return (
            entity.get("label")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("name")
            or ""
        ).strip()

    def _entity_key(self, entity: dict) -> str:
        return self._normalize(self._entity_name(entity))

    def _tokenize(self, text: str):
        return [t for t in re.split(r"[^\wáéíóúñü]+", self._normalize(text)) if t]

    def _clip_score(self, value, default=0.0):
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return default

    def _is_allowed_type(self, t: str) -> bool:
        return bool(t) and str(t).strip() in self.allowed_types

    def _clean_type_list(self, types_list):
        cleaned = []
        for t in self._as_list(types_list):
            t = str(t).strip()
            if t and self._is_allowed_type(t):
                cleaned.append(t)
        return self._dedupe(cleaned)

    # =========================================================
    # Reglas estructurales
    # =========================================================

    def _is_hard_bad_entity(self, entity: dict) -> bool:
        label = self._entity_key(entity)
        if not label:
            return True

        if label in self.hard_bad_exact:
            return True

        if any(label.endswith(sfx) for sfx in self.hard_bad_suffixes):
            return True

        if re.fullmatch(r"[\W_0-9]+", label):
            return True

        return False

    def _clean_address(self, entity: dict):
        address = self._clean_text(entity.get("address", ""))
        low = self._normalize(address)

        if not address:
            entity["address"] = ""
            return entity

        if any(fragment in low for fragment in self.bad_address_fragments):
            entity["address"] = ""
            return entity

        entity["address"] = address
        return entity

    def _clean_phone(self, entity: dict):
        phone = self._clean_text(entity.get("phone", ""))

        if phone in self.global_phone_values:
            entity["phone"] = ""
            return entity

        entity["phone"] = phone
        return entity

    def _clean_email(self, entity: dict):
        entity["email"] = self._clean_text(entity.get("email", ""))
        return entity

    def _drop_global_email_for_non_org(self, entity: dict):
        email = self._clean_text(entity.get("email", "")).lower()
        if not email:
            return entity

        if email not in self.global_email_values:
            return entity

        entity_class = str(entity.get("class", "")).strip()
        entity_types = {str(t).strip() for t in self._as_list(entity.get("type")) if str(t).strip()}

        allowed_classes = {"Organization", "EventOrganisationCompany"}
        if entity_class not in allowed_classes and not (entity_types & allowed_classes):
            entity["email"] = ""

        return entity

    def _clean_related_urls(self, entity: dict):
        urls = self._normalize_related_urls(entity.get("relatedUrls", ""))
        label = self._entity_key(entity)
        tokens = [t for t in self._tokenize(label) if len(t) > 3]

        if not urls:
            entity["relatedUrls"] = []
            return entity

        broad_entities = {
            "sevilla",
            "semana santa",
            "cuaresma",
            "real alcazar",
            "real alcázar",
        }

        if label in broad_entities:
            entity["relatedUrls"] = urls[:10]
            return entity

        filtered = []
        for u in urls:
            ul = self._normalize(u)
            if tokens and any(tok in ul for tok in tokens):
                filtered.append(u)

        if not filtered and urls:
            filtered = urls[:1]

        entity["relatedUrls"] = self._dedupe(filtered[:8])
        return entity

    def _clean_descriptions(self, entity: dict):
        for field in ["short_description", "long_description", "description"]:
            entity[field] = self._clean_text(entity.get(field, ""))
        return entity

    def _clean_images(self, entity: dict):
        image = self._clean_text(entity.get("image", ""))
        main_image = self._clean_text(entity.get("mainImage", ""))

        props = entity.get("properties", {}) or {}
        props_main_image = self._first_nonempty(props.get("mainImage", ""))
        props_image = self._first_nonempty(props.get("image", ""))

        entity["image"] = image if image.startswith(("http://", "https://")) else ""
        entity["mainImage"] = main_image if main_image.startswith(("http://", "https://")) else ""

        if not entity["image"] and props_image.startswith(("http://", "https://")):
            entity["image"] = props_image

        if not entity["mainImage"] and props_main_image.startswith(("http://", "https://")):
            entity["mainImage"] = props_main_image

        candidate = props.get("candidateImage")
        if candidate:
            candidate = self._clean_text(candidate)
            if not candidate.startswith(("http://", "https://")):
                props.pop("candidateImage", None)
            else:
                props["candidateImage"] = candidate

        entity["properties"] = props
        return entity

    # =========================================================
    # Tipado final preservando el ranker
    # =========================================================

    def _infer_type_from_label(self, label: str):
        if not label:
            return None

        # Eventos
        if label in {
            "semana santa",
            "feria de sevilla",
            "vela de triana",
            "temporada taurina",
            "pregon",
            "pregón",
            "madruga",
            "madrugá",
            "miercoles de ceniza",
            "miércoles de ceniza",
            "viernes santo",
            "domingo de ramos",
            "cuaresma",
            "seminci",
        }:
            return "Event"

        # Patrimonio / cultura
        if "museo" in label:
            return "Museum"
        if "castillo" in label:
            return "Castle"
        if "alcazar" in label or "alcázar" in label:
            return "Alcazar"
        if "catedral" in label:
            return "Cathedral"
        if "basilica" in label or "basílica" in label:
            return "Basilica"
        if "capilla" in label:
            return "Chapel"
        if "iglesia" in label:
            return "Church"
        if "abadia" in label or "abadía" in label:
            return "HistoricalOrCulturalResource"
        if "monasterio" in label:
            return "HistoricalOrCulturalResource"
        if "convento" in label:
            return "HistoricalOrCulturalResource"
        if "plaza de toros" in label:
            return "BullRing"
        if "plaza" in label:
            return "Square"
        if "ayuntamiento" in label:
            return "TownHall"
        if "estadio" in label:
            return "Stadium"
        if "estatua" in label or "escultura" in label:
            return "Monument"
        if "yacimiento" in label or "arqueologic" in label or "arqueológic" in label:
            return "ArcheologicalSite"
        if "centro cultural" in label:
            return "CultureCenter"
        if "sala de exposiciones" in label:
            return "ExhibitionHall"
        if "academia" in label:
            return "EducationalCenter"

        # Negocio / servicios
        if "hotel" in label or "hostal" in label or "apartamento turistico" in label or "apartamento turístico" in label:
            return "AccommodationEstablishment"
        if (
            "restaurante" in label
            or "cafeteria" in label
            or "cafetería" in label
            or re.search(r"\bbar\b", label)
        ):
            return "FoodEstablishment"
        if "outlet" in label or "fashion" in label or "shopping" in label:
            return "RetailAndFashion"
        if (
            "oficina de turismo" in label
            or "punto de informacion turistica" in label
            or "punto de información turística" in label
        ):
            return "TourismService"
        if (
            "taxi" in label
            or "aeropuerto" in label
            or "estacion" in label
            or "estación" in label
            or "bus turistico" in label
            or "autobus turistico" in label
        ):
            return "TransportInfrastructure"
        if "parking" in label or "aparcamiento" in label:
            return "PublicService"

        return None

    def _resolve_final_class_and_types(self, entity: dict):
        """
        Prioridad:
        1. normalized_type del ranker
        2. class existente si es válida
        3. primer type válido
        4. inferencia por label
        5. Thing
        """
        label = self._entity_key(entity)

        normalized_type = str(entity.get("normalized_type", "")).strip()
        current_class = str(entity.get("class", "")).strip()
        current_types = self._clean_type_list(entity.get("type"))

        inferred_type = self._infer_type_from_label(label)

        # Candidato principal
        if self._is_allowed_type(normalized_type):
            final_class = normalized_type
        elif self._is_allowed_type(current_class):
            final_class = current_class
        elif current_types:
            final_class = current_types[0]
        elif inferred_type and self._is_allowed_type(inferred_type):
            final_class = inferred_type
        else:
            final_class = "Thing"

        final_types = []

        # Mantener el principal delante
        final_types.append(final_class)

        # Conservar normalized_type si aporta algo
        if self._is_allowed_type(normalized_type) and normalized_type not in final_types:
            final_types.append(normalized_type)

        # Conservar class actual si es válida y distinta
        if self._is_allowed_type(current_class) and current_class not in final_types:
            final_types.append(current_class)

        # Conservar types previos válidos
        for t in current_types:
            if t not in final_types:
                final_types.append(t)

        # Añadir inferido si ayuda
        if inferred_type and self._is_allowed_type(inferred_type) and inferred_type not in final_types:
            final_types.append(inferred_type)

        # Limpiar redundancias demasiado genéricas si ya hay algo específico
        has_specific = any(t not in self.generic_types for t in final_types)
        if has_specific:
            final_types = [t for t in final_types if t not in self.generic_types or t == final_class]

        entity["class"] = final_class
        entity["type"] = self._dedupe(final_types[:5])

        return entity

    def _preserve_ranking_features(self, entity: dict):
        entity["score"] = self._clip_score(entity.get("score"), default=0.0)

        if "final_score" in entity:
            entity["final_score"] = self._clip_score(entity.get("final_score"), default=entity["score"])
            entity["score"] = max(entity["score"], entity["final_score"])
        else:
            entity["final_score"] = entity["score"]

        if "semantic_similarity" in entity:
            entity["semantic_similarity"] = self._clip_score(entity.get("semantic_similarity"), default=0.0)

        if "name_similarity" in entity:
            entity["name_similarity"] = self._clip_score(entity.get("name_similarity"), default=0.0)

        if "class_similarity" in entity:
            entity["class_similarity"] = self._clip_score(entity.get("class_similarity"), default=0.0)

        try:
            if "class_distance" in entity:
                entity["class_distance"] = int(entity["class_distance"])
        except Exception:
            entity["class_distance"] = 999

        return entity

    def _ensure_top_level_fields(self, entity: dict):
        props = entity.get("properties", {}) or {}

        if not entity.get("sourceUrl") and props.get("sourceUrl"):
            entity["sourceUrl"] = props.get("sourceUrl")

        if not entity.get("url") and props.get("url"):
            entity["url"] = props.get("url")

        if not entity.get("relatedUrls") and props.get("relatedUrls"):
            entity["relatedUrls"] = props.get("relatedUrls")

        if not entity.get("description") and props.get("description"):
            entity["description"] = props.get("description")

        if not entity.get("image") and props.get("image"):
            entity["image"] = props.get("image")

        if not entity.get("mainImage") and props.get("mainImage"):
            entity["mainImage"] = props.get("mainImage")

        return entity

    # =========================================================
    # Duplicados parciales / nombres truncados
    # =========================================================

    def _is_more_specific(self, a: dict, b: dict) -> bool:
        name_a = self._entity_name(a)
        name_b = self._entity_name(b)

        qa = a.get("qualityScore", 0)
        qb = b.get("qualityScore", 0)

        if qa != qb:
            return qa > qb

        fa = a.get("final_score", a.get("score", 0))
        fb = b.get("final_score", b.get("score", 0))
        if fa != fb:
            return fa > fb

        da = a.get("class_distance", 999)
        db = b.get("class_distance", 999)
        if da != db:
            return da < db

        if len(name_a) != len(name_b):
            return len(name_a) > len(name_b)

        ra = len(a.get("relatedUrls", []) or [])
        rb = len(b.get("relatedUrls", []) or [])
        return ra > rb

    def _remove_substring_duplicates(self, entities: list) -> list:
        kept = []

        norm = []
        for e in entities:
            name = self._entity_name(e)
            norm.append((e, self._normalize(name), len(name)))

        for i, (e_i, n_i, l_i) in enumerate(norm):
            if not n_i:
                continue

            drop = False
            for j, (e_j, n_j, l_j) in enumerate(norm):
                if i == j:
                    continue
                if n_i == n_j:
                    continue

                if n_i in n_j and l_j > l_i:
                    if self._is_more_specific(e_j, e_i):
                        drop = True
                        break

            if not drop:
                kept.append(e_i)

        return kept

    # =========================================================
    # API pública
    # =========================================================

    def process(self, entities: list) -> list:
        out = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            entity = dict(entity)

            entity = self._ensure_top_level_fields(entity)

            if self._is_hard_bad_entity(entity):
                continue

            entity = self._clean_address(entity)
            entity = self._clean_phone(entity)
            entity = self._clean_email(entity)
            entity = self._clean_related_urls(entity)
            entity = self._clean_descriptions(entity)
            entity = self._clean_images(entity)

            # 🔥 Preservar señales del ranker antes de tocar tipos
            entity = self._preserve_ranking_features(entity)

            # 🔥 Resolver class/type final sin destruir normalized_type
            entity = self._resolve_final_class_and_types(entity)

            entity = self._drop_global_email_for_non_org(entity)

            quality = self.quality_scorer.evaluate(entity)
            entity["qualityScore"] = quality["score"]
            entity["qualityFlags"] = quality["flags"]
            entity["qualityDecision"] = quality["decision"]

            if quality["decision"] == "discard":
                continue

            if quality["decision"] == "review":
                entity["needsReview"] = True

            visible_name = self._entity_name(entity)
            if not visible_name:
                continue

            out.append(entity)

        out = self._remove_substring_duplicates(out)

        return out