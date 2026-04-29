from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable, List, Optional

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from src.linking.wikidata_linker import WikidataLinker


class KnowledgeGraphBuilder:
    def __init__(self):
        self.EX = Namespace("http://example.org/resource/")
        self.TOUR = Namespace("http://example.org/tourism/")
        self.wikidata_linker = WikidataLinker()
        self.max_images = 3

        self.generic_types = {
            "",
            "Thing",
            "Entity",
            "Unknown",
            "Location",
            "TourismEntity",
            "TourismResource",
        }

        self.name_noise_suffixes = [
            " pago recomendado",
            " también",
            " comenzaremos",
            " ver",
            " más",
            " tambien",
        ]

        self.bad_image_fragments = [
            "logo",
            "icon",
            "sprite",
            "banner",
            "placeholder",
            "header",
            "footer",
            "og-image",
            "share",
            "social",
            "favicon",
            "_next/static/",
            "_next/image?",
            "/static/media/",
            ".svg",
            "gobiernoes_ministerio",
        ]

    # =========================
    # Helpers de normalización
    # =========================

    def _slugify(self, text: str) -> str:
        text = text or ""
        text = text.strip().lower()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "_", text).strip("_")
        return text or "entity"

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

    def _dedupe_preserve_order(self, values: Iterable[Any]) -> List[Any]:
        seen = set()
        out = []
        for v in values:
            key = str(v).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(v)
        return out

    def _local_name(self, value: Any) -> str:
        txt = self._normalize_space(str(value or ""))
        if not txt:
            return ""
        return txt.split("#")[-1].split("/")[-1].strip()

    # =========================
    # Helpers Wikidata
    # =========================

    def _commons_filename_to_url(self, filename: str) -> str:
        filename = self._normalize_space(filename)
        if not filename:
            return ""

        if filename.startswith("http://") or filename.startswith("https://"):
            return filename

        low = filename.lower()
        if low.startswith("file:"):
            filename = filename[5:].strip()
        elif low.startswith("archivo:"):
            filename = filename[8:].strip()

        safe_name = filename.replace(" ", "_")
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{safe_name}"

    def _safe_get_wikidata_payload(self, wikidata_id: str) -> dict:
        if not wikidata_id or not self.wikidata_linker:
            return {}

        # compatibilidad con varias implementaciones
        for method_name in ("get_entity_data", "fetch_entity_data", "_get_entity_data"):
            if hasattr(self.wikidata_linker, method_name):
                method = getattr(self.wikidata_linker, method_name)
                try:
                    payload = method(wikidata_id)
                    return payload or {}
                except Exception:
                    return {}
        return {}

    def _safe_link_wikidata(
        self,
        entity_name: str,
        entity_class: str,
        short_description: str,
        long_description: str,
        source_url: str,
        aliases: Optional[List[str]] = None,
    ) -> str:
        if not self.wikidata_linker:
            return ""

        aliases = aliases or []

        try:
            return (
                self.wikidata_linker.link(
                    entity_name=entity_name,
                    entity_class=entity_class,
                    short_description=short_description,
                    long_description=long_description,
                    source_url=source_url,
                    aliases=aliases,
                )
                or ""
            )
        except TypeError:
            try:
                return (
                    self.wikidata_linker.link(
                        entity_name,
                        entity_class,
                        short_description,
                        long_description,
                        source_url,
                    )
                    or ""
                )
            except Exception:
                return ""
        except Exception:
            return ""

    def _enrich_entity_with_wikidata(self, entity: dict, wikidata_payload: dict) -> dict:
        if not isinstance(entity, dict):
            return entity

        if not isinstance(wikidata_payload, dict):
            return entity

        qid = wikidata_payload.get("wikidata_id") or wikidata_payload.get("id")
        if qid and not entity.get("wikidata_id") and not entity.get("wikidataId"):
            entity["wikidata_id"] = qid

        coords = entity.get("coordinates")
        if not isinstance(coords, dict):
            coords = {}

        lat = coords.get("lat")
        lng = coords.get("lng")

        if lat in (None, "") and wikidata_payload.get("latitude") is not None:
            coords["lat"] = wikidata_payload.get("latitude")

        if lng in (None, "") and wikidata_payload.get("longitude") is not None:
            coords["lng"] = wikidata_payload.get("longitude")

        if coords:
            entity["coordinates"] = coords

        if entity.get("latitude") in (None, "") and wikidata_payload.get("latitude") is not None:
            entity["latitude"] = wikidata_payload.get("latitude")

        if entity.get("longitude") in (None, "") and wikidata_payload.get("longitude") is not None:
            entity["longitude"] = wikidata_payload.get("longitude")

        wikidata_image = self._commons_filename_to_url(wikidata_payload.get("image", ""))

        if wikidata_image and self._is_probably_good_image(wikidata_image):
            if not entity.get("image"):
                entity["image"] = wikidata_image
            if not entity.get("mainImage"):
                entity["mainImage"] = wikidata_image

            props = entity.get("properties")
            if not isinstance(props, dict):
                props = {}

            if not props.get("image"):
                props["image"] = wikidata_image
            if not props.get("mainImage"):
                props["mainImage"] = wikidata_image

            entity["properties"] = props

        return entity

    # =========================
    # Filtros de calidad
    # =========================

    def _is_bad_name(self, value: str) -> bool:
        v = self._normalize_space(value)
        vl = v.lower()

        if not v:
            return True

        bad_exact = {
            "mainimage",
            "image",
            "mapas",
            "vista",
            "aquí",
            "aqui",
            "qué ver",
            "que ver",
        }
        if vl in bad_exact:
            return True

        if re.fullmatch(r"\d+[_-]?", v):
            return True
        if re.fullmatch(r"[A-Za-z]?\d+[_-]?[A-Za-z]?", v):
            return True

        bad_fragments = [
            "leer más",
            "leer mas",
            "mostrar más",
            "mostrar mas",
            "reserva tu actividad",
            "ir al contenido",
            "todos los derechos reservados",
            "accesibilidad",
            "guías convention bureau",
            "guias convention bureau",
            "área profesional",
            "area profesional",
        ]
        return any(b in vl for b in bad_fragments)

    def _looks_like_url(self, value: str) -> bool:
        v = self._normalize_space(value)
        return v.startswith("http://") or v.startswith("https://")

    def _is_probably_good_image(self, value: str) -> bool:
        v = self._normalize_space(value)
        if not self._looks_like_url(v):
            return False

        vl = v.lower()

        if any(b in vl for b in self.bad_image_fragments):
            return False

        valid_exts = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"]
        if not any(ext in vl for ext in valid_exts):
            return False

        return True

    def _clean_text(self, value: str) -> str:
        v = self._normalize_space(value)
        if not v:
            return ""

        noisy_markers = [
            " Leer más",
            " leer más",
            " Leer mas",
            " leer mas",
            " Mostrar más",
            " mostrar más",
            " Mostrar mas",
            " mostrar mas",
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

    def _strip_name_suffix_noise(self, value: str) -> str:
        txt = self._clean_text(value)
        low = txt.lower()

        for suffix in self.name_noise_suffixes:
            if low.endswith(suffix):
                txt = txt[: -len(suffix)].strip(" -|,.;:")
                low = txt.lower()

        txt = re.sub(r"\b(PAGO RECOMENDADO|También|Tambien|Comenzaremos|Ver)\b$", "", txt, flags=re.IGNORECASE).strip(" -|,.;:")
        return txt

    def _choose_display_name(self, entity: dict) -> str:
        label = self._strip_name_suffix_noise(entity.get("label", ""))
        entity_name = self._strip_name_suffix_noise(entity.get("entity_name", ""))
        entity_base = self._strip_name_suffix_noise(entity.get("entity", ""))

        raw_name = entity.get("name", "")
        name_candidates = self._as_list(raw_name)
        name_candidates = [
            self._strip_name_suffix_noise(n)
            for n in name_candidates
            if self._strip_name_suffix_noise(n)
        ]

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

        semantic_type = self._clean_text(entity.get("semantic_type", ""))
        if semantic_type:
            values.append(self._local_name(semantic_type))

        properties = entity.get("properties", {}) or {}
        if isinstance(properties, dict):
            prop_type = self._clean_text(properties.get("type", ""))
            if prop_type:
                values.append(self._local_name(prop_type))

        # closed-world enriched fields
        values.extend(self._as_list(entity.get("types")))
        values.extend(self._as_list(entity.get("typesRaw")))
        values.extend(self._as_list(entity.get("types_raw")))

        cleaned = []
        for v in values:
            txt = self._local_name(v)
            if txt and txt not in self.generic_types:
                cleaned.append(txt)

        return self._dedupe_preserve_order(cleaned)[:self.max_images]

    def _extract_best_entity_type(self, entity: dict) -> str:
        candidates = []

        for key in ("class", "type", "semantic_type", "primaryClass"):
            value = entity.get(key)
            if isinstance(value, (list, tuple)):
                candidates.extend([self._local_name(v) for v in value if self._local_name(v)])
            else:
                txt = self._local_name(value)
                if txt:
                    candidates.append(txt)

        properties = entity.get("properties", {}) or {}
        if isinstance(properties, dict):
            prop_type = self._local_name(properties.get("type", ""))
            if prop_type:
                candidates.append(prop_type)

        for candidate in candidates:
            if candidate and candidate not in self.generic_types:
                return candidate

        return ""

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
            else:
                items.append(raw.strip())

        items = [x for x in items if self._looks_like_url(x)]
        return self._dedupe_preserve_order(items)

    def _extract_candidate_images(self, entity: dict) -> List[str]:
        properties = entity.get("properties", {}) or {}
        if not isinstance(properties, dict):
            properties = {}

        values = []
        values.extend(self._as_list(entity.get("image")))
        values.extend(self._as_list(entity.get("mainImage")))
        values.extend(self._as_list(entity.get("images")))
        values.extend(self._as_list(entity.get("additionalImages")))

        values.extend(self._as_list(properties.get("image")))
        values.extend(self._as_list(properties.get("mainImage")))
        values.extend(self._as_list(properties.get("images")))
        values.extend(self._as_list(properties.get("additionalImages")))
        values.extend(self._as_list(properties.get("candidateImage")))

        cleaned = []
        for value in values:
            txt = self._clean_text(str(value))
            if txt and self._is_probably_good_image(txt):
                cleaned.append(txt)

        return self._dedupe_preserve_order(cleaned)

    def _should_skip_entity(self, entity: dict) -> bool:
        label = self._clean_text(entity.get("label", ""))
        name = self._choose_display_name(entity)
        combined = f"{label} {name}".lower()

        if not combined.strip():
            return True

        if self._is_bad_name(name):
            return True

        return False

    # =========================
    # Añadir triples
    # =========================

    def _add_literal_if_value(self, g: Graph, subject: URIRef, predicate: URIRef, value: Any, datatype=None):
        if value is None:
            return

        if isinstance(value, (list, tuple)):
            for item in value:
                self._add_literal_if_value(g, subject, predicate, item, datatype=datatype)
            return

        if isinstance(value, dict):
            return

        text = str(value).strip()
        if not text:
            return

        lit = Literal(text, datatype=datatype) if datatype else Literal(text)
        g.add((subject, predicate, lit))

    def _add_unique_string_list(self, g: Graph, subject: URIRef, predicate: URIRef, values: List[str]):
        values = [self._normalize_space(v) for v in values if self._normalize_space(v)]
        values = self._dedupe_preserve_order(values)
        for v in values:
            g.add((subject, predicate, Literal(v)))

    def _add_coordinates(self, g: Graph, subject: URIRef, entity: dict):
        coords = entity.get("coordinates") or {}
        lat = coords.get("lat") if isinstance(coords, dict) else None
        lng = coords.get("lng") if isinstance(coords, dict) else None

        if lat in (None, ""):
            lat = entity.get("latitude")
        if lng in (None, ""):
            lng = entity.get("longitude")

        try:
            if lat not in (None, ""):
                g.add((subject, self.TOUR.latitude, Literal(float(lat), datatype=XSD.float)))
            if lng not in (None, ""):
                g.add((subject, self.TOUR.longitude, Literal(float(lng), datatype=XSD.float)))
        except Exception:
            pass

    # =========================
    # API pública
    # =========================

    def build_graph(self, entities: list) -> Graph:
        g = Graph()
        g.bind("ex", self.EX)
        g.bind("tour", self.TOUR)
        g.bind("rdfs", RDFS)

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            if self._should_skip_entity(entity):
                continue

            display_name = self._choose_display_name(entity)
            subject = URIRef(self.EX[self._slugify(display_name)])

            g.add((subject, RDF.type, self.TOUR.Entity))
            g.add((subject, self.TOUR.label, Literal(display_name)))
            g.add((subject, RDFS.label, Literal(display_name)))

            raw_name_values = self._as_list(entity.get("name"))
            clean_names = []
            for n in raw_name_values:
                n = self._strip_name_suffix_noise(str(n))
                if n and not self._is_bad_name(n) and n != display_name:
                    clean_names.append(n)
            clean_names = self._dedupe_preserve_order(clean_names)
            self._add_unique_string_list(g, subject, self.TOUR.name, clean_names)

            types_ = self._extract_types(entity)
            self._add_unique_string_list(g, subject, self.TOUR.type, types_)

            score = entity.get("score")
            if score is not None:
                try:
                    g.add((subject, self.TOUR.score, Literal(float(score), datatype=XSD.float)))
                except Exception:
                    pass

            source_url = self._clean_text(entity.get("sourceUrl", ""))
            if self._looks_like_url(source_url):
                g.add((subject, self.TOUR.sourceUrl, Literal(source_url)))

            page_url = self._clean_text(entity.get("url", ""))
            if self._looks_like_url(page_url):
                g.add((subject, self.TOUR.url, Literal(page_url)))

            related_urls = self._extract_related_urls(entity)
            self._add_unique_string_list(g, subject, self.TOUR.relatedUrls, related_urls)

            short_description = self._clean_text(
                entity.get("short_description")
                or entity.get("shortDescription")
                or ""
            )
            long_description = self._clean_text(
                entity.get("long_description")
                or entity.get("longDescription")
                or ""
            )
            description = self._clean_multiline_text(entity.get("description", ""))
            address = self._clean_text(entity.get("address", ""))

            self._add_literal_if_value(g, subject, self.TOUR.shortDescription, short_description)
            self._add_literal_if_value(g, subject, self.TOUR.longDescription, long_description)
            self._add_literal_if_value(g, subject, self.TOUR.description, description)
            self._add_literal_if_value(g, subject, self.TOUR.address, address)

            phone = self._clean_text(entity.get("phone", ""))
            email = self._clean_text(entity.get("email", ""))
            self._add_literal_if_value(g, subject, self.TOUR.phone, phone)
            self._add_literal_if_value(g, subject, self.TOUR.email, email)

            self._add_coordinates(g, subject, entity)

            entity_name = self._clean_text(
                entity.get("entity_name")
                or entity.get("name")
                or entity.get("label")
                or display_name
            )

            entity_class = self._extract_best_entity_type(entity)

            wikidata_source_url = self._clean_text(
                entity.get("url")
                or entity.get("sourceUrl")
            )

            wikidata_id = (
                entity.get("wikidata_id")
                or entity.get("wikidataId")
                or (entity.get("properties", {}) or {}).get("wikidata_id")
                or (entity.get("properties", {}) or {}).get("wikidataId")
                or ""
            )

            if not wikidata_id:
                wikidata_id = self._safe_link_wikidata(
                    entity_name=entity_name,
                    entity_class=entity_class,
                    short_description=short_description,
                    long_description=long_description,
                    source_url=wikidata_source_url,
                    aliases=[display_name, entity_name],
                )

            if wikidata_id:
                wikidata_payload = self._safe_get_wikidata_payload(wikidata_id)
                entity = self._enrich_entity_with_wikidata(entity, wikidata_payload)

            wikidata_value = (
                entity.get("wikidata_id")
                or entity.get("wikidataId")
                or wikidata_id
                or ""
            )

            if wikidata_value:
                try:
                    self._add_literal_if_value(g, subject, self.TOUR.wikidataId, wikidata_value)
                except Exception as e:
                    print(f"⚠️ Error añadiendo wikidataId para {display_name}: {e}")

            # Coordenadas otra vez, por si Wikidata las completó
            self._add_coordinates(g, subject, entity)

            candidate_images = self._extract_candidate_images(entity)
            if candidate_images:
                primary_image = entity.get("image") or candidate_images[0]
                main_image = entity.get("mainImage") or (
                    candidate_images[1] if len(candidate_images) > 1 else candidate_images[0]
                )
                if main_image == primary_image and len(candidate_images) > 1:
                    main_image = candidate_images[1]

                self._add_literal_if_value(g, subject, self.TOUR.image, primary_image)
                self._add_literal_if_value(g, subject, self.TOUR.mainImage, main_image)

                if len(candidate_images) > 1:
                    self._add_unique_string_list(
                        g,
                        subject,
                        self.TOUR.additionalImages,
                        candidate_images[1:self.max_images],
                    )

        return g

    def save_graph(self, graph: Graph, output_path: str = "knowledge_graph.ttl"):
        graph.serialize(destination=output_path, format="turtle")
