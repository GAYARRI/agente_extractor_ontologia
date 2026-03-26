# src/page_entity_resolver.py

import re
import unicodedata
from difflib import SequenceMatcher


class PageEntityResolver:
    def __init__(self):
        pass

    # =========================================================
    # Helpers básicos
    # =========================================================

    def normalize_key(self, text: str) -> str:
        text = text or ""
        text = text.strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def similar(self, a: str, b: str, threshold: float = 0.92) -> bool:
        a_n = self.normalize_key(a)
        b_n = self.normalize_key(b)

        if not a_n or not b_n:
            return False

        if a_n == b_n:
            return True

        return SequenceMatcher(None, a_n, b_n).ratio() >= threshold

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

    def _clean_text(self, text: str) -> str:
        text = (text or "").strip()
        text = re.sub(r"\s+", " ", text)

        noisy_markers = [
            " Leer más",
            " leer más",
            " Mostrar más",
            " mostrar más",
        ]
        for marker in noisy_markers:
            idx = text.find(marker)
            if idx > 0:
                text = text[:idx].strip(" -|,.;:")

        return text.strip()

    def _looks_like_url(self, value: str) -> bool:
        v = (value or "").strip()
        return v.startswith("http://") or v.startswith("https://")

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

        items = [x for x in items if self._looks_like_url(str(x).strip())]
        return self._dedupe_preserve_order(items)

    # =========================================================
    # Matching / agrupación
    # =========================================================

    def same_entity(self, cand: dict, group: dict) -> bool:
        name = cand.get("entity_name") or cand.get("entity") or cand.get("label") or ""
        gname = group.get("entity_name") or group.get("entity") or group.get("label") or ""

        if self.similar(name, gname):
            return True

        props = cand.get("properties", {}) or {}
        gprops = group.get("properties", {}) or {}

        for key in ("phone", "email", "address"):
            v1 = str(props.get(key) or cand.get(key) or "").strip().lower()
            v2 = str(gprops.get(key) or group.get(key) or "").strip().lower()
            if v1 and v2 and v1 == v2:
                return True

        c1 = cand.get("coordinates") or {}
        c2 = group.get("coordinates") or {}
        if c1.get("lat") and c2.get("lat") and c1.get("lng") and c2.get("lng"):
            if str(c1["lat"]) == str(c2["lat"]) and str(c1["lng"]) == str(c2["lng"]):
                return True

        return False

    # =========================================================
    # Nombres
    # =========================================================

    def is_bad_name(self, name: str) -> bool:
        n = (name or "").strip()
        nl = n.lower()

        if not n:
            return True

        bad_exact = {
            "comer y salir en sevilla - visita sevilla",
            "saborea sevilla barrio a barrio",
            "visita sevilla",
            "consejos, rutas y curiosidades gastronómicas",
            "mainimage",
            "image",
            "candidateimage",
        }
        if nl in bad_exact:
            return True

        if re.fullmatch(r"\d+[_-]?", n):
            return True
        if re.fullmatch(r"[A-Za-z]?\d+[_-]?[A-Za-z]?", n):
            return True

        if len(n) > 60:
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
        if any(b in nl for b in bad_fragments):
            return True

        return False

    def choose_best_name(self, names):
        names = [self._clean_text(str(n)) for n in names if self._clean_text(str(n))]
        if not names:
            return ""

        def score_name(n: str) -> int:
            score = 0
            nl = n.lower()

            if self.is_bad_name(n):
                score -= 10

            if re.fullmatch(r"[\W_0-9]+", n):
                score -= 10
            if len(n) < 3:
                score -= 5
            if len(n) > 80:
                score -= 5

            words = n.split()
            if 1 <= len(words) <= 5:
                score += 4
            if n[:1].isupper():
                score += 2
            if n.istitle():
                score += 2

            if any(bad in nl for bad in ["castillo", "mercado", "arenal", "sevilla", "triana", "san jorge"]):
                score += 1

            return score

        names = sorted(names, key=score_name, reverse=True)
        return names[0]

    def repair_name_fields(self, entity: dict) -> dict:
        label = (entity.get("label") or "").strip()
        entity_name = (entity.get("entity_name") or "").strip()
        entity_base = (entity.get("entity") or "").strip()
        name = (entity.get("name") or "").strip()

        candidates = [label, entity_name, entity_base]
        good = ""

        for c in candidates:
            if c and not self.is_bad_name(c):
                good = c
                break

        if not good:
            return entity

        if self.is_bad_name(name) or (name and len(name) > len(good) + 15):
            entity["name"] = good

        if self.is_bad_name(entity_name):
            entity["entity_name"] = good

        if self.is_bad_name(entity_base):
            entity["entity"] = good

        if not label or self.is_bad_name(label):
            entity["label"] = good

        return entity

    # =========================================================
    # Propiedades / limpieza
    # =========================================================

    def merge_properties(self, base: dict, extra: dict) -> dict:
        out = dict(base or {})

        for k, v in (extra or {}).items():
            if v in (None, "", [], {}):
                continue

            if k not in out or out[k] in (None, "", [], {}):
                out[k] = v
            elif isinstance(out[k], list) and isinstance(v, list):
                out[k] = self._dedupe_preserve_order(out[k] + v)
            elif out[k] != v:
                if isinstance(out[k], list):
                    current = out[k]
                else:
                    current = [out[k]]

                incoming = v if isinstance(v, list) else [v]
                out[k] = self._dedupe_preserve_order(current + incoming)

        return out

    def clean_placeholder_properties(self, entity: dict) -> dict:
        props = entity.get("properties", {}) or {}

        for key in ["image", "mainImage", "candidateImage"]:
            value = props.get(key)
            if isinstance(value, str) and value.strip().lower() == key.lower():
                props.pop(key, None)

        if entity.get("image") == "image":
            entity["image"] = ""
        if entity.get("mainImage") == "mainImage":
            entity["mainImage"] = ""

        entity["properties"] = props
        return entity

    def clean_noisy_fields(self, entity: dict) -> dict:
        noisy_markers = ["leer más", "mostrar más"]

        for field in ["address", "description", "short_description", "long_description", "name"]:
            value = entity.get(field)
            if not isinstance(value, str):
                continue

            vl = value.lower()
            for marker in noisy_markers:
                idx = vl.find(marker)
                if idx > 0:
                    value = value[:idx].strip(" -|,.;:")
                    break

            entity[field] = value.strip()

        return entity

    # =========================================================
    # Imágenes
    # =========================================================

    def dedupe_images_across_entities(self, entities: list) -> list:
        image_map = {}

        for idx, e in enumerate(entities):
            props = e.get("properties", {}) or {}
            img = (props.get("image") or e.get("image") or "").strip()
            name = (e.get("entity_name") or e.get("entity") or "").strip().lower()

            if not img:
                continue

            image_map.setdefault(img, []).append((idx, name))

        for img, items in image_map.items():
            if len(items) <= 1:
                continue

            img_l = img.lower()
            scored = []

            for idx, name in items:
                score = 0
                tokens = [t for t in re.split(r"[\s\-_]+", name) if len(t) > 3]
                if tokens and any(t in img_l for t in tokens):
                    score += 3
                scored.append((idx, score))

            scored.sort(key=lambda x: x[1], reverse=True)

            if len(set(score for _, score in scored)) == 1 and scored[0][1] == 0:
                continue

            winner_idx = scored[0][0]

            for idx, _score in scored[1:]:
                props = entities[idx].get("properties", {}) or {}
                if props.get("image") == img:
                    props.pop("image", None)
                    entities[idx]["properties"] = props
                if entities[idx].get("image") == img:
                    entities[idx]["image"] = ""
                if entities[idx].get("mainImage") == img:
                    entities[idx]["mainImage"] = ""

        return entities

    def _extract_all_image_candidates(self, e: dict):
        props = e.get("properties", {}) or {}
        imgs = []

        for key in ["image", "mainImage", "additionalImages"]:
            val = e.get(key)
            if val:
                if isinstance(val, list):
                    imgs.extend(val)
                else:
                    imgs.append(val)

            valp = props.get(key)
            if valp:
                if isinstance(valp, list):
                    imgs.extend(valp)
                else:
                    imgs.append(valp)

        flat = []
        for img in imgs:
            if not img:
                continue
            s = str(img).strip()

            if s.startswith("[") and s.endswith("]"):
                inner = s[1:-1].strip()
                parts = [p.strip(" '\"") for p in inner.split(",") if p.strip(" '\"")]
                flat.extend(parts)
            elif "|" in s:
                flat.extend([x.strip() for x in s.split("|") if x.strip()])
            else:
                flat.append(s)

        return self._dedupe_preserve_order(flat)

    def remove_repeated_global_images(self, entities: list, threshold: int = 5) -> list:
        counter = {}

        for e in entities:
            for img in self._extract_all_image_candidates(e):
                counter[img] = counter.get(img, 0) + 1

        for e in entities:
            props = e.get("properties", {}) or {}

            filtered = []
            for img in self._extract_all_image_candidates(e):
                low = img.lower()
                if counter.get(img, 0) >= threshold:
                    continue
                if any(b in low for b in ["separador", "separator", "logo", "banner", "icon", "header", "footer"]):
                    continue
                filtered.append(img)

            filtered = self._dedupe_preserve_order(filtered)

            if filtered:
                e["image"] = filtered[0]
                e["mainImage"] = filtered[0]
                props["image"] = filtered[0]
                props["mainImage"] = filtered[0]
                if len(filtered) > 1:
                    props["additionalImages"] = filtered[1:]
                else:
                    props.pop("additionalImages", None)
            else:
                e["image"] = ""
                e["mainImage"] = ""
                props.pop("image", None)
                props.pop("mainImage", None)
                props.pop("additionalImages", None)

            e["properties"] = props

        return entities

    def promote_unique_candidate_images(self, entities: list) -> list:
        candidate_counts = {}

        for e in entities:
            props = e.get("properties", {}) or {}
            cand = (props.get("candidateImage") or "").strip()

            if not cand:
                continue

            candidate_counts[cand] = candidate_counts.get(cand, 0) + 1

        for e in entities:
            props = e.get("properties", {}) or {}
            cand = (props.get("candidateImage") or "").strip()

            if not cand:
                continue

            if (e.get("image") or "").strip() or (e.get("mainImage") or "").strip():
                continue

            low = cand.lower()

            if any(bad in low for bad in [
                "logo", "icon", "banner", "separator", "separador",
                "header", "footer", "placeholder", "avatar", "share", "social"
            ]):
                continue

            if candidate_counts.get(cand, 0) == 1:
                e["image"] = cand
                e["mainImage"] = cand
                props["image"] = cand
                props["mainImage"] = cand

            e["properties"] = props

        return entities

    # =========================================================
    # Filtro editorial / duplicados parciales
    # =========================================================

    def is_editorial_entity(self, entity: dict) -> bool:
        text = " ".join([
            str(entity.get("label", "")),
            str(entity.get("name", "")),
            str(entity.get("entity_name", "")),
            str(entity.get("description", "")),
            str(entity.get("short_description", "")),
            str(entity.get("long_description", "")),
        ]).lower()

        bad_patterns = [
            "leer más",
            "mostrar más",
            "consejos, rutas",
            "descubre sevilla",
            "bajo el cielo de sevilla",
            "ruta gastro",
            "saborea sevilla barrio a barrio",
            "comer y salir en sevilla",
            "día internacional de la cerveza",
        ]

        bad_labels = {
            "sevilla leer",
            "sevilla cuando",
            "recorrer sevilla",
        }

        label = str(entity.get("label", "")).strip().lower()
        name = str(entity.get("name", "")).strip().lower()

        if label in bad_labels or name in bad_labels:
            return True

        return any(p in text for p in bad_patterns)

    def remove_substring_entities(self, entities: list) -> list:
        kept = []

        normalized = []
        for e in entities:
            name = (
                e.get("label")
                or e.get("entity_name")
                or e.get("entity")
                or e.get("name")
                or ""
            ).strip()
            normalized.append((e, self.normalize_key(name), len(name)))

        for i, (entity_i, name_i, len_i) in enumerate(normalized):
            if not name_i:
                continue

            drop = False
            for j, (_entity_j, name_j, len_j) in enumerate(normalized):
                if i == j:
                    continue
                if name_i == name_j:
                    continue
                if name_i in name_j and len_j > len_i:
                    drop = True
                    break

            if not drop:
                kept.append(entity_i)

        return kept

    # =========================================================
    # Resolución principal
    # =========================================================

    def resolve(self, entities: list) -> list:
        groups = []

        for e in entities:
            matched = None
            for g in groups:
                if self.same_entity(e, g):
                    matched = g
                    break

            current_name = (
                e.get("entity_name")
                or e.get("entity")
                or e.get("label")
                or ""
            )

            current_props = e.get("properties", {}) or {}
            current_image = (
                current_props.get("image")
                or e.get("image")
                or e.get("mainImage")
                or ""
            )

            current_related = self._normalize_related_urls(e.get("relatedUrls", ""))

            if matched is None:
                groups.append({
                    "entity": e.get("entity", current_name),
                    "entity_name": current_name,
                    "label": e.get("label", current_name),
                    "name": e.get("name", current_name),
                    "class": e.get("class", ""),
                    "type": e.get("type", e.get("class", "")),
                    "score": e.get("score", 0.0),
                    "verisimilitude_score": e.get("verisimilitude_score", e.get("score", 0.0)),
                    "properties": current_props,
                    "address": e.get("address", ""),
                    "phone": e.get("phone", ""),
                    "email": e.get("email", ""),
                    "coordinates": e.get("coordinates", {"lat": None, "lng": None}),
                    "short_description": e.get("short_description", ""),
                    "long_description": e.get("long_description", ""),
                    "description": e.get("description", ""),
                    "wikidata_id": e.get("wikidata_id", ""),
                    "sourceUrl": e.get("sourceUrl", ""),
                    "relatedUrls": current_related,
                    "url": e.get("url", ""),
                    "image": e.get("image", ""),
                    "mainImage": e.get("mainImage", ""),
                    "_names": [current_name, e.get("name", ""), e.get("label", "")],
                    "_images": [current_image],
                })
            else:
                matched["_names"].extend([
                    current_name,
                    e.get("name", ""),
                    e.get("label", "")
                ])
                matched["_images"].append(current_image)

                matched["score"] = max(
                    matched.get("score", 0.0),
                    e.get("score", 0.0)
                )
                matched["verisimilitude_score"] = max(
                    matched.get("verisimilitude_score", 0.0),
                    e.get("verisimilitude_score", e.get("score", 0.0))
                )

                matched["properties"] = self.merge_properties(
                    matched.get("properties", {}),
                    current_props
                )

                if not matched.get("address") and e.get("address"):
                    matched["address"] = e.get("address")
                if not matched.get("phone") and e.get("phone"):
                    matched["phone"] = e.get("phone")
                if not matched.get("email") and e.get("email"):
                    matched["email"] = e.get("email")
                if not matched.get("short_description") and e.get("short_description"):
                    matched["short_description"] = e.get("short_description")
                if not matched.get("long_description") and e.get("long_description"):
                    matched["long_description"] = e.get("long_description")
                if not matched.get("description") and e.get("description"):
                    matched["description"] = e.get("description")
                if not matched.get("wikidata_id") and e.get("wikidata_id"):
                    matched["wikidata_id"] = e.get("wikidata_id")

                if not matched.get("sourceUrl") and e.get("sourceUrl"):
                    matched["sourceUrl"] = e.get("sourceUrl")

                if not matched.get("url") and e.get("url"):
                    matched["url"] = e.get("url")

                new_related = self._normalize_related_urls(e.get("relatedUrls", ""))
                if new_related:
                    old_related = matched.get("relatedUrls", [])
                    matched["relatedUrls"] = self._dedupe_preserve_order(old_related + new_related)

                c = matched.get("coordinates") or {}
                ec = e.get("coordinates") or {}
                if not c.get("lat") and ec.get("lat"):
                    matched["coordinates"] = ec

                if not matched.get("class") and e.get("class"):
                    matched["class"] = e.get("class")
                if not matched.get("type") and e.get("type"):
                    matched["type"] = e.get("type")

        resolved = []

        for g in groups:
            best_name = self.choose_best_name(g.pop("_names", []))
            best_image = ""
            image_candidates = g.pop("_images", [])
            image_candidates = [img for img in image_candidates if isinstance(img, str) and img.strip()]
            if image_candidates:
                best_image = image_candidates[0]

            if best_name:
                g["entity"] = best_name
                g["entity_name"] = best_name
                if not g.get("label"):
                    g["label"] = best_name
                if not g.get("name"):
                    g["name"] = best_name

            if best_image:
                g["properties"]["image"] = best_image
                if not g.get("image"):
                    g["image"] = best_image
                if not g.get("mainImage"):
                    g["mainImage"] = best_image

            try:
                g = self.repair_name_fields(g)
            except Exception as e:
                print(f"⚠️ Error reparando nombres: {e}")

            g = self.clean_placeholder_properties(g)
            g = self.clean_noisy_fields(g)

            resolved.append(g)

        resolved = self.dedupe_images_across_entities(resolved)
        resolved = self.remove_repeated_global_images(resolved, threshold=5)
        resolved = self.promote_unique_candidate_images(resolved)
        resolved = [e for e in resolved if not self.is_editorial_entity(e)]
        resolved = self.remove_substring_entities(resolved)

        return resolved