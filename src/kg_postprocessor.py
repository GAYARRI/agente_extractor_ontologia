# src/kg_postprocessor.py

import re
import unicodedata

from src.entity_quality_scorer import EntityQualityScorer


class KGPostProcessor:
    def __init__(self):
        self.quality_scorer = EntityQualityScorer()

        # señales bastante universales de ruido editorial o truncado
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

        allowed_classes = {"Organization", "LocalBusiness"}
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

        candidate = props.get("candidateImage")
        if candidate:
            candidate = self._clean_text(candidate)
            if not candidate.startswith(("http://", "https://")):
                props.pop("candidateImage", None)
            else:
                props["candidateImage"] = candidate

        entity["properties"] = props
        return entity

    def _normalize_types(self, entity: dict):
        raw_types = []
        raw_types.extend(self._as_list(entity.get("type")))
        raw_types.extend(self._as_list(entity.get("class")))

        cleaned = []
        for t in raw_types:
            t = str(t).strip()
            if t:
                cleaned.append(t)

        cleaned = self._dedupe(cleaned)

        label = self._entity_key(entity)

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
        }:
            return ["Event"]

        if label in {"ruta de los azulejos", "ruta de la opera", "ruta de la ópera"}:
            return ["Route"]

        if label in {"ayuntamiento de sevilla"}:
            return ["Organization"]

        if label in {"sevilla sin gluten", "red sevilla sin gluten", "red sevilla"}:
            return ["LocalBusiness"]

        if label in {"patrimonio inmaterial"}:
            return ["CulturalHeritage"]

        if "mercado" in label:
            return ["TouristAttraction", "Place"]

        if any(word in label for word in ["castillo", "capilla", "hospital", "catedral", "alcazar", "alcázar"]):
            return ["TouristAttraction"]

        preferred = [t for t in cleaned if t != "Location"]

        if not preferred:
            preferred = ["Place"]

        return self._dedupe(preferred)

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

            entity["type"] = self._normalize_types(entity)

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