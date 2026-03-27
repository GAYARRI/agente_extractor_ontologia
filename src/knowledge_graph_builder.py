# src/knowledge_graph_builder.py

import re
import unicodedata
from typing import Any, Iterable, List

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD
from src.linking.wikidata_linker import WikidataLinker


class KnowledgeGraphBuilder:
    def __init__(self):
        self.EX = Namespace("http://example.org/resource/")
        self.TOUR = Namespace("http://example.org/tourism/")
        self.wikidata_linker = WikidataLinker()

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
        text = re.sub(r"\s+", " ", str(text)).strip()
        return text

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

    # =========================
    # Filtros de calidad
    # =========================

    def _is_bad_name(self, value: str) -> bool:
        v = self._normalize_space(value)
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

    def _looks_like_url(self, value: str) -> bool:
        v = self._normalize_space(value)
        return v.startswith("http://") or v.startswith("https://")

    def _is_probably_good_image(self, value: str) -> bool:
        v = self._normalize_space(value)
        if not self._looks_like_url(v):
            return False

        vl = v.lower()
        bad = [
            "logo", "icon", "sprite", "banner", "placeholder",
            "header", "footer", "og-image", "share", "social"
        ]
        if any(b in vl for b in bad):
            return False

        return True

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
            else:
                items.append(raw.strip())

        items = [x for x in items if self._looks_like_url(x)]
        return self._dedupe_preserve_order(items)

    def _should_skip_entity(self, entity: dict) -> bool:
        label = self._clean_text(entity.get("label", ""))
        name = self._choose_display_name(entity)
        combined = f"{label} {name}".lower()

        if not combined.strip():
            return True

        bad_entities = {
            "sevilla leer",
            "sevilla cuando",
        }
        if label.lower() in bad_entities or name.lower() in bad_entities:
            return True

        return False

    # =========================
    # Añadir triples
    # =========================

    def _add_literal_if_value(self, g: Graph, subject: URIRef, predicate: URIRef, value: Any, datatype=None):
        if value is None:
            return

        text = str(value).strip()
        if not text:
            return

        lit = Literal(value, datatype=datatype) if datatype else Literal(value)
        g.add((subject, predicate, lit))

    def _add_unique_string_list(self, g: Graph, subject: URIRef, predicate: URIRef, values: List[str]):
        values = [self._normalize_space(v) for v in values if self._normalize_space(v)]
        values = self._dedupe_preserve_order(values)
        for v in values:
            g.add((subject, predicate, Literal(v)))

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

            # name: solo si es bueno y distinto del label
            raw_name_values = self._as_list(entity.get("name"))
            clean_names = []
            for n in raw_name_values:
                n = self._clean_text(str(n))
                if n and not self._is_bad_name(n) and n != display_name:
                    clean_names.append(n)
            clean_names = self._dedupe_preserve_order(clean_names)
            self._add_unique_string_list(g, subject, self.TOUR.name, clean_names)

            # tipos
            types_ = self._extract_types(entity)
            self._add_unique_string_list(g, subject, self.TOUR.type, types_)

            # score
            score = entity.get("score")
            if score is not None:
                try:
                    g.add((subject, self.TOUR.score, Literal(float(score), datatype=XSD.float)))
                except Exception:
                    pass

            # urls
            source_url = self._clean_text(entity.get("sourceUrl", ""))
            if self._looks_like_url(source_url):
                g.add((subject, self.TOUR.sourceUrl, Literal(source_url)))

            page_url = self._clean_text(entity.get("url", ""))
            if self._looks_like_url(page_url):
                g.add((subject, self.TOUR.url, Literal(page_url)))

            related_urls = self._extract_related_urls(entity)
            self._add_unique_string_list(g, subject, self.TOUR.relatedUrls, related_urls)

            # textos
            short_description = self._clean_text(entity.get("short_description", ""))
            long_description = self._clean_text(entity.get("long_description", ""))
            description = self._clean_multiline_text(entity.get("description", ""))
            address = self._clean_text(entity.get("address", ""))

            self._add_literal_if_value(g, subject, self.TOUR.shortDescription, short_description)
            self._add_literal_if_value(g, subject, self.TOUR.longDescription, long_description)
            self._add_literal_if_value(g, subject, self.TOUR.description, description)
            self._add_literal_if_value(g, subject, self.TOUR.address, address)

            # contacto
            phone = self._clean_text(entity.get("phone", ""))
            email = self._clean_text(entity.get("email", ""))
            self._add_literal_if_value(g, subject, self.TOUR.phone, phone)
            self._add_literal_if_value(g, subject, self.TOUR.email, email)

            # coordenadas
            coords = entity.get("coordinates") or {}
            lat = coords.get("lat")
            lng = coords.get("lng")
            try:
                if lat not in (None, ""):
                    g.add((subject, self.TOUR.latitude, Literal(float(lat), datatype=XSD.float)))
                if lng not in (None, ""):
                    g.add((subject, self.TOUR.longitude, Literal(float(lng), datatype=XSD.float)))
            except Exception:
                pass
 
            entity_name = self._clean_text(
            entity.get("entity_name")
            or entity.get("name")
            or entity.get("label")
            or display_name
        )

        entity_class = self._clean_text(entity.get("class")) or "Thing"

        wikidata_source_url = self._clean_text(
            entity.get("url")
            or entity.get("sourceUrl")
        )

        wikidata_id = self.wikidata_linker.link(
            entity_name=entity_name,
            entity_class=entity_class,
            short_description=short_description,
            long_description=long_description,
            source_url=wikidata_source_url,
        )

        self._add_literal_if_value(g, subject, self.TOUR.wikidataId, wikidata_id)
                
                
        # imágenes: solo si son claramente buenas
        properties = entity.get("properties", {}) or {}
        candidate_images = [
            entity.get("image", ""),
            entity.get("mainImage", ""),
            properties.get("image", ""),
            properties.get("mainImage", ""),
        ]
        candidate_images = [self._clean_text(x) for x in candidate_images if self._clean_text(x)]
        candidate_images = self._dedupe_preserve_order(candidate_images)
        candidate_images = [img for img in candidate_images if self._is_probably_good_image(img)]

        if candidate_images:
            g.add((subject, self.TOUR.image, Literal(candidate_images[0])))
            g.add((subject, self.TOUR.mainImage, Literal(candidate_images[0])))

        return g

    def save_graph(self, graph: Graph, output_path: str = "knowledge_graph.ttl"):
        graph.serialize(destination=output_path, format="turtle")