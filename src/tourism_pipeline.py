from src.html_block_extractor import HTMLBlockExtractor
from src.tourism_entity_extractor import TourismEntityExtractor
from src.entity_cleaner import EntityCleaner
from src.entities.entity_deduplicator import EntityDeduplicator
from src.entities.entity_normalizer import EntityNormalizer
from src.entity_expander import EntityExpander
from src.entities.entity_splitter import EntitySplitter
from src.ontology_index import OntologyIndex
from src.poi.poi_discovery import POIDiscovery
from src.events.event_detector import EventDetector
from src.semantic.semantic_type_guesser import SemanticTypeGuesser
from src.semantic.semantic_similarity_matcher import SemanticSimilarityMatcher
from src.semantic.relation_extractor import RelationExtractor
from src.property_enricher import PropertyEnricher
from src.linking.wikidata_linker import WikidataLinker
from src.description_extractor import DescriptionExtractor
from src.image_enricher import ImageEnricher
from src.llm.llm_supervisor import LLMSupervisor
from src.entities.entity_ranker import EntityRanker
from src.entities.entity_clusterer import EntityClusterer
from src.entities.entity_scorer import EntityScorer
from src.entities.global_entity_memory import GlobalEntityMemory
from src.entities.entity_graph_builder import EntityGraphBuilder
from src.tourism_property_extractor import TourismPropertyExtractor
from src.page_entity_resolver import PageEntityResolver
from src.dom_image_resolver import DOMImageResolver

import re
import hashlib
import os
from urllib.parse import urlparse, urlunparse, unquote
from difflib import SequenceMatcher
from bs4 import BeautifulSoup


def normalize_text(text):
    text = text.lower()
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def text_hash(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def is_similar(a, b, threshold=0.90):
    return SequenceMatcher(None, a, b).ratio() > threshold


def fix_encoding(text):
    try:
        return text.encode("latin1").decode("utf-8")
    except Exception:
        return text


class TourismPipeline:
    def __init__(self, ontology_path):
        self.block_extractor = HTMLBlockExtractor()
        self.entity_extractor = TourismEntityExtractor()
        self.cleaner = EntityCleaner()
        self.deduplicator = EntityDeduplicator()
        self.normalizer = EntityNormalizer()
        self.expander = EntityExpander()
        self.splitter = EntitySplitter()
        self.ontology_index = OntologyIndex(ontology_path)
        self.poi_discovery = POIDiscovery()
        self.event_detector = EventDetector()
        self.type_guesser = SemanticTypeGuesser()
        self.semantic_matcher = SemanticSimilarityMatcher(self.ontology_index)
        self.relation_extractor = RelationExtractor()
        self.property_enricher = PropertyEnricher(self.ontology_index)
        self.wikidata_linker = WikidataLinker()
        self.description_extractor = DescriptionExtractor()
        self.image_enricher = ImageEnricher()
        self.llm_supervisor = LLMSupervisor(self.ontology_index)
        self.ranker = EntityRanker()
        self.clusterer = EntityClusterer()
        self.global_memory = GlobalEntityMemory()
        self.entity_scorer = EntityScorer()
        self.graph_builder = EntityGraphBuilder()
        self.tourism_property_extractor = TourismPropertyExtractor()
        self.page_entity_resolver = PageEntityResolver()
        self.dom_image_resolver = DOMImageResolver()

        self.edge_stopwords = {
            "de", "del", "la", "las", "el", "los", "y", "e", "en", "por",
            "para", "con", "sin", "a", "al", "un", "una", "uno", "unas",
            "unos", "si", "te", "tu", "sus", "su", "lo", "que", "como"
        }

        self.portal_category_terms = {
            "monumentos", "museos", "agenda", "cultura", "artesanía",
            "fiestas", "deporte", "ocio", "familia", "parques", "barrios",
            "compras", "gastronomía", "conciertos", "exposiciones",
            "actividades", "rutas", "mapas", "horarios", "alojamientos",
            "visitas", "planes", "contactos", "información", "informacion",
            "guías", "guias", "idioma", "moneda", "comer", "salir"
        }

        self.ui_noise_patterns = [
            "google analytics",
            "esta web utiliza",
            "te has suscrito",
            "watch later",
            "copy link",
            "share",
            "suscrito satisfactoriamente",
            "cookies",
            "privacidad",
            "aviso legal",
            "política de cookies",
            "politica de cookies",
            "páginas más populares",
            "paginas más populares",
            "número de visitantes",
            "numero de visitantes",
            "ir a página",
            "ir a pagina",
            "ver listado",
            "haz clic aquí",
            "haz clic aqui"
        ]

        self.navigation_patterns = [
            "qué hacer",
            "que hacer",
            "prepara tu viaje",
            "durante tu estancia",
            "cómo moverte",
            "como moverte",
            "ideas y planes",
            "monumentos y museos",
            "comer y salir",
            "ocio y familia",
            "de compras",
            "puntos de información turística",
            "puntos de informacion turistica"
        ]

    # ==================================================
    # IMAGE HELPERS
    # ==================================================

    def _normalize_image_url(self, url):
        if not url:
            return None

        url = str(url).strip()
        if not url:
            return None

        parsed = urlparse(url)

        clean = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            "",
            ""
        ))

        return unquote(clean)

    def _image_signature(self, url):
        if not url:
            return None

        norm = self._normalize_image_url(url)
        if not norm:
            return None

        path = unquote(urlparse(norm).path).lower()
        filename = os.path.basename(path)

        if not filename:
            return path

        thumb_prefixes = [
            "120px-", "150px-", "180px-", "200px-", "220px-", "250px-",
            "300px-", "320px-", "400px-", "500px-", "640px-", "800px-",
            "1024px-"
        ]

        for prefix in thumb_prefixes:
            if filename.startswith(prefix):
                filename = filename[len(prefix):]
                break

        return filename

    def _dedupe_images(self, images):
        result = []
        seen = set()

        for img in images:
            norm = self._normalize_image_url(img)
            sig = self._image_signature(norm)

            if not norm or not sig:
                continue

            if sig in seen:
                continue

            seen.add(sig)
            result.append(norm)

        return result

    def _normalize_final_image_props(self, props):
        if not props:
            return {}

        local_images = []

        for key in ("mainImage", "image"):
            value = props.get(key)
            if value and not self._is_wikimedia_url(value):
                local_images.append(value)

        additional = props.get("additionalImages")
        if isinstance(additional, list):
            for img in additional:
                if img and not self._is_wikimedia_url(img):
                    local_images.append(img)
        elif additional and not self._is_wikimedia_url(additional):
            local_images.append(additional)

        local_images = self._dedupe_images(local_images)

        if local_images:
            props["mainImage"] = local_images[0]
            props["image"] = local_images[0]

            if len(local_images) > 1:
                props["additionalImages"] = local_images[1:]
            else:
                props.pop("additionalImages", None)
        else:
            props.pop("mainImage", None)
            props.pop("image", None)
            props.pop("additionalImages", None)

        wikidata_image = props.get("wikidataImage")
        if wikidata_image:
            wikidata_norm = self._normalize_image_url(wikidata_image)
            wikidata_sig = self._image_signature(wikidata_norm)

            local_sigs = {self._image_signature(img) for img in local_images if img}

            if not wikidata_sig or wikidata_sig in local_sigs:
                props.pop("wikidataImage", None)
            else:
                props["wikidataImage"] = wikidata_norm
        else:
            props.pop("wikidataImage", None)

        return props

    def _resolve_dom_image(self, html, entity, url=""):
        """
        Devuelve (image_url, score)
        """
        try:
            if hasattr(self.dom_image_resolver, "resolve_with_score"):
                return self.dom_image_resolver.resolve_with_score(
                    html=html,
                    entity_name=entity,
                    base_url=url,
                    min_score=0,
                )
        except Exception:
            pass

        try:
            if hasattr(self.dom_image_resolver, "resolve"):
                img = self.dom_image_resolver.resolve(
                    html=html,
                    entity_name=entity,
                    base_url=url,
                    min_score=0,
                )
                return img, 3 if img else 0
        except Exception:
            pass

        try:
            if hasattr(self.dom_image_resolver, "resolve_image_for_entity"):
                img = self.dom_image_resolver.resolve_image_for_entity(html, entity)
                return img, 3 if img else 0
        except Exception:
            pass

        return "", 0    
        

    # ==================================================
    # NUEVOS HELPERS OUTPUT
    # ==================================================

    def _safe_string(self, value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _safe_float(self, value):
        if value is None or value == "":
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _looks_like_email(self, value):
        if not value:
            return False

        return re.fullmatch(
            r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
            value.strip()
        ) is not None

    def _extract_email_from_text(self, text):
        if not text:
            return ""

        match = re.search(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
            text,
            flags=re.IGNORECASE,
        )
        return match.group(0).strip() if match else ""

    def _extract_email_from_html(self, html):
        if not html:
            return ""

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return ""

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if href.lower().startswith("mailto:"):
                email = href[7:].split("?")[0].strip()
                if self._looks_like_email(email):
                    return email

        visible_text = soup.get_text(" ", strip=True)
        return self._extract_email_from_text(visible_text)

    def _build_coordinates(self, props):
        lat = self._safe_float(props.get("latitude"))
        lng = self._safe_float(props.get("longitude"))

        if lat is not None and not (-90 <= lat <= 90):
            lat = None

        if lng is not None and not (-180 <= lng <= 180):
            lng = None

        return {
            "lat": lat,
            "lng": lng
        }

    def _build_output_entity(
        self,
        entity,
        label,
        score,
        props,
        short_description="",
        long_description="",
        wikidata_id=None,
        html="",
        text="",
        url=""
    ):
        short_description = self._safe_string(short_description)
        long_description = self._safe_string(long_description)

        fallback_desc = self._safe_string(props.get("description"))

        if not short_description:
            short_description = fallback_desc[:180] if fallback_desc else ""

        if not long_description:
            long_description = fallback_desc

    
        email = (
            self._safe_string(props.get("email"))
            or self._safe_string(props.get("correo"))
        )

        if not self._looks_like_email(email):
            email = ""    
        

        if not self._looks_like_email(email):
            email = ""

        props = self._normalize_final_image_props(props if isinstance(props, dict) else {})

        return {
            "entity": self._safe_string(entity),
            "entity_name": self._safe_string(entity),
            "label": self._safe_string(entity),
            "name": self._safe_string(entity),
            "class": self._safe_string(label) or "Place",
            "type": [self._safe_string(label) or "Place", "Location"],
            "score": float(score) if score is not None else 0.0,
            "verisimilitude_score": float(score) if score is not None else 0.0,
            "sourceUrl": self._safe_string(url),
            "properties": props,
            "short_description": short_description,
            "long_description": long_description,
            "description": fallback_desc,
            "address": self._safe_string(props.get("address")),
            "phone": self._safe_string(props.get("telephone") or props.get("phone")),
            "email": email,
            "coordinates": self._build_coordinates(props),
            "wikidata_id": wikidata_id,
            "image": self._safe_string(props.get("image")),
            "mainImage": self._safe_string(props.get("mainImage")),
            "relatedUrls": self._safe_string(props.get("relatedUrls")),
            "url": self._safe_string(props.get("url")),
        }

    # ==================================================
    # VALIDACIÓN GENERAL
    # ==================================================

    def is_valid_entity(self, entity):
        if not entity:
            return False

        e = entity.lower()
        words = entity.split()

        if len(entity) < 3:
            return False

        if len(words) > 7:
            return False

        if "Ã" in entity:
            return False

        if re.fullmatch(r"[\d\W_]+", entity):
            return False

        return True

    def is_valid_block(self, text):
        if not text:
            return False

        t = text.lower().strip()

        if len(t) < 35:
            return False

        if any(
            x in t
            for x in [
                "password",
                "login",
                "register",
                "social media"
            ]
        ):
            return False

        return True

    # ==================================================
    # FILTRO DE BLOQUES
    # ==================================================

    def is_cookie_or_ui_block(self, text):
        t = normalize_text(text)
        return any(pattern in t for pattern in self.ui_noise_patterns)

    def is_navigation_block(self, text):
        t = normalize_text(text)

        if any(pattern in t for pattern in self.navigation_patterns):
            return True

        words = re.findall(r"\b[\wáéíóúñü]+\b", t, flags=re.IGNORECASE)
        if not words:
            return False

        category_hits = sum(1 for w in words if w in self.portal_category_terms)

        if len(words) <= 25 and category_hits >= max(4, len(words) // 3):
            return True

        if len(words) <= 18 and category_hits >= 5:
            return True

        return False

    def is_contact_card_block(self, text):
        t = normalize_text(text)

        signals = 0

        if re.search(r"\+?\d[\d\s\-]{7,}", t):
            signals += 1

        if re.search(r"\b(410\d{2}|41\d{3}|cp\b|código postal|codigo postal)\b", t):
            signals += 1

        if any(
            x in t for x in [
                "av.", "avenida", "calle", "plaza", "s/n", "km.", "km ",
                "teléfono", "telefono", "teléfonos", "telefonos",
                "conexiones", "paradas de taxi", "líneas de autobús",
                "lineas de autobus", "metro", "web", "contacto"
            ]
        ):
            signals += 1

        if any(
            x in t for x in [
                "aeropuerto", "estación", "estacion", "muelle",
                "terminal", "radio taxi", "tele taxi", "oficina de turismo"
            ]
        ):
            signals += 1

        return signals >= 2

    # ==================================================
    # LIMPIEZA DE ENTIDADES
    # ==================================================

    def clean_entity_edges(self, entity):
        if not entity:
            return entity

        words = entity.split()
        if not words:
            return entity

        while words and words[0].lower() in self.edge_stopwords:
            words.pop(0)

        while words and words[-1].lower() in self.edge_stopwords:
            words.pop()

        cleaned = " ".join(words).strip(" ,.;:-")
        return cleaned

    def is_code_like_entity(self, entity):
        if not entity:
            return False

        e = entity.strip()

        if re.fullmatch(r"[A-Z]*\d+[A-Z\d\s\-]*", e):
            return True

        if re.fullmatch(r"\d{3,}", e):
            return True

        if re.fullmatch(r"(?:[A-Z]\d|[A-Z]{1,3}\d{1,3})(?:\s+[A-Z]\d|\s+[A-Z]{1,3}\d{1,3})*", e):
            return True

        if re.fullmatch(r"\d{1,2}:\d{2}", e):
            return True

        return False

    def is_low_value_entity(self, entity, block_text=""):
        if not entity:
            return True

        e = self.clean_entity_edges(entity)
        if not e:
            return True

        low = e.lower().strip()
        tokens = [t for t in re.findall(r"\b[\wáéíóúñü]+\b", low, flags=re.IGNORECASE) if t]

        if not tokens:
            return True

        if len(e) < 3:
            return True

        if self.is_code_like_entity(e):
            return True

        if any(x in low for x in ["google analytics", "gracias te", "páginas más populares", "paginas más populares"]):
            return True

        if low in {
            "cultura", "ocio", "familia", "compras", "moneda", "idioma",
            "horarios", "mapas", "guías", "guias", "autobús", "autobus",
            "taxi", "metro", "parking", "festivales", "fiestas",
            "museos", "monumentos", "gastronomía", "gastronomia",
            "paradas de taxi", "líneas de autobús", "lineas de autobus",
            "eventos deportivos", "actividades en familia", "planes culturales",
            "medios de transporte", "puntos de información", "puntos de informacion",
            "información turística", "informacion turistica", "visitas guiadas",
            "servicios de emergencia", "patrimonio monumental"
        }:
            return True

        if len(tokens) >= 2:
            if e == e.lower():
                generic_heads = {
                    "eventos", "actividades", "planes", "medios", "puntos",
                    "servicios", "visitas", "conexiones", "horarios",
                    "información", "informacion", "patrimonio"
                }
                if any(tok in generic_heads for tok in tokens):
                    return True

        if all(token in self.portal_category_terms for token in tokens):
            return True

        if len(tokens) >= 2 and sum(1 for token in tokens if token in self.portal_category_terms) >= len(tokens) - 1:
            return True

        if re.search(r"\b\d{4,5}\b", low) and len(tokens) <= 3:
            return True

        if re.search(r"\b(km|av|s/n|gmt)\b", low) and len(tokens) <= 4:
            return True

        if any(token in self.edge_stopwords for token in tokens[:1] + tokens[-1:]):
            return True

        if len(tokens) >= 3 and all(token in self.portal_category_terms or token in self.edge_stopwords for token in tokens):
            return True

        if any(
            x in low for x in [
                "ir a página", "ir a pagina", "ver listado",
                "teléfonos de atención", "telefonos de atencion",
                "puntos de información", "puntos de informacion"
            ]
        ):
            return True

        return False

    def smart_trim(self, entity):
        entity = self.clean_entity_edges(entity)
        words = entity.split()

        if len(words) <= 4:
            return entity

        if "de" in [w.lower() for w in words]:
            return entity

        return " ".join(words[-4:])

    # ==================================================
    # EXTRACCIÓN DE ENTIDAD PRINCIPAL EN FICHAS
    # ==================================================

    def extract_primary_entity_from_contact_block(self, text):
        if not text:
            return None

        candidates = [
            r"\b(Aeropuerto de [A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+)*)",
            r"\b(Estación de tren [A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+)*)",
            r"\b(Estación de [A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+)*)",
            r"\b(Terminal de cruceros [A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+)*)",
            r"\b(Muelle de las [A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+)*)",
            r"\b(Estación de autobuses [A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+)*)",
            r"\b(Parking de Autobuses\s*-\s*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+)*)",
            r"\b(Radio Taxi Sevilla)\b",
            r"\b(Tele Taxi Sevilla)\b",
            r"\b(Metro Sevilla)\b",
            r"\b(Metrocentro)\b",
            r"\b(Sevici)\b",
            r"\b(Ayuntamiento de Sevilla)\b",
            r"\b(Oficinas? de Turismo)\b",
        ]

        for pattern in candidates:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        first_chunk = re.split(r"[.:|]|(?:\s{2,})", text)[0].strip()
        first_chunk = self.clean_entity_edges(first_chunk)

        if first_chunk and 4 <= len(first_chunk) <= 80:
            if not self.is_low_value_entity(first_chunk, text):
                return first_chunk

        return None

    # ==================================================
    # PROPIEDADES
    # ==================================================

    def _merge_properties(self, *prop_dicts):
        merged = {}
        local_image_keys = {"image", "mainImage", "additionalImages"}
        local_images = []
        wikidata_image = None

        for props in prop_dicts:
            if not props:
                continue

            for key, value in props.items():
                if value is None or value == "":
                    continue

                if key == "wikidataImage":
                    if value and not wikidata_image:
                        wikidata_image = value
                    continue

                if key in local_image_keys:
                    if isinstance(value, list):
                        local_images.extend(value)
                    else:
                        local_images.append(value)
                    continue

                if key not in merged:
                    merged[key] = value
                    continue

                old_value = merged[key]

                if old_value == value:
                    continue

                if isinstance(old_value, list):
                    existing = old_value
                else:
                    existing = [old_value]

                if isinstance(value, list):
                    incoming = value
                else:
                    incoming = [value]

                for item in incoming:
                    if item not in existing:
                        existing.append(item)

                merged[key] = existing

        local_images = [
            img for img in local_images
            if img
            and not self._is_wikimedia_url(img)
            and "separador" not in str(img).lower()
            and "separator" not in str(img).lower()
            and "logo" not in str(img).lower()
            and "banner" not in str(img).lower()
        ]    
            
        local_images = self._dedupe_images(local_images)

        if local_images:
            merged["mainImage"] = local_images[0]
            merged["image"] = local_images[0]

            if len(local_images) > 1:
                merged["additionalImages"] = local_images[1:]

        if wikidata_image:
            merged["wikidataImage"] = wikidata_image

        merged = self._normalize_final_image_props(merged)

        for key, value in list(merged.items()):
            if isinstance(value, list) and key != "additionalImages":
                merged[key] = " | ".join(str(v) for v in value if v)

        return merged

    # ==================================================
    # RELACIONES
    # ==================================================

    def sanitize_relations(self, relations):
        clean_relations = []

        for rel in relations or []:
            subject = (rel.get("subject") or "").strip()
            relation = (rel.get("relation") or "").strip()
            obj = (rel.get("object") or "").strip()

            if not subject or not relation or not obj:
                continue

            if len(subject.split()) > 8:
                continue

            if len(obj.split()) > 8:
                continue

            if self.is_low_value_entity(subject):
                continue

            if self.is_low_value_entity(obj):
                continue

            clean_relations.append({
                "subject": subject,
                "relation": relation,
                "object": obj
            })

        return clean_relations

    # ==================================================
    # PIPELINE
    # ==================================================

    def run(self, html, url=""):
        blocks = self.block_extractor.extract(html)
        results = []
        seen_texts = []
        seen_hashes = set()

        for block in blocks:
            text = block.get("text", "") if isinstance(block, dict) else block
            text = fix_encoding(text or "").strip()

            if not text:
                continue

            normalized = normalize_text(text)
            h = text_hash(normalized)

            is_exact_dup = h in seen_hashes
            is_near_dup = any(is_similar(normalized, seen) for seen in seen_texts)

            seen_texts.append(normalized)
            seen_hashes.add(h)

            if is_exact_dup and not self.has_entity_signal(text):
                continue

            if is_near_dup and not self.has_entity_signal(text):
                continue

            if not self.is_valid_block(text) and not self.has_entity_signal(text):
                continue

            if self.is_cookie_or_ui_block(text):
                continue

            if self.is_navigation_block(text):
                continue

            print("\n--- TEXTO BLOQUE ---")
            print(text[:120])

            entities = []

            if self.is_contact_card_block(text):
                primary = self.extract_primary_entity_from_contact_block(text)
                if primary:
                    entities.append(primary)

            try:
                ner_entities = self.entity_extractor.extract(text) or []
                entities.extend(ner_entities)
            except Exception:
                pass

            try:
                llm_entities_raw = self.llm_supervisor.extract_and_validate_entities(text) or []
                for item in llm_entities_raw:
                    if isinstance(item, dict):
                        value = item.get("entity") or item.get("name") or item.get("label")
                        if value:
                            entities.append(value)
                    elif isinstance(item, str):
                        entities.append(item)
            except Exception:
                pass

            try:
                detected_events = self.event_detector.detect(text) or []
                for item in detected_events:
                    if isinstance(item, dict):
                        value = item.get("entity") or item.get("name") or item.get("label")
                        if value:
                            entities.append(value)
                    elif isinstance(item, str):
                        entities.append(item)
            except Exception:
                pass

            try:
                detected_pois = self.poi_discovery.discover(text) or []
                for item in detected_pois:
                    if isinstance(item, dict):
                        value = item.get("entity") or item.get("name") or item.get("label")
                        if value:
                            entities.append(value)
                    elif isinstance(item, str):
                        entities.append(item)
            except Exception:
                pass

            entities = self.cleaner.clean(entities)
            entities = [self.clean_entity_edges(e) for e in entities if self.is_valid_entity(e)]
            entities = [e for e in entities if e]

            entities = self.deduplicator.deduplicate(entities)
            entities = self.normalizer.normalize(entities)

            split_entities = []
            for e in entities:
                parts = self.splitter.split(e)
                split_entities.extend(parts if parts else [e])

            entities = split_entities
            entities = [self.smart_trim(e) for e in entities]
            entities = [self.clean_entity_edges(e) for e in entities]
            entities = [e for e in entities if e]

            entities = [e for e in entities if not self.is_low_value_entity(e, text)]

            final_entities = []
            seen_entities = set()
            for e in entities:
                key = e.lower().strip()
                if key not in seen_entities:
                    seen_entities.add(key)
                    final_entities.append(e)

            entities = final_entities

            print("ENTIDADES FINAL:", entities)

            if not entities:
                continue

            classified_entities = []

            try:
                llm_entities = self.llm_supervisor.analyze_entities(entities, text)
            except Exception:
                llm_entities = []

            if not llm_entities:
                for entity in entities:
                    page_props = self.tourism_property_extractor.extract(
                        html=html,
                        text=text,
                        url=url,
                        entity=entity,
                    ) or {}

                    try:
                        image_props = self.image_enricher.enrich(
                            entity=entity,
                            text=text,
                            html=html,
                        ) or {}
                    except Exception:
                        image_props = {}

                    dom_image, dom_score = self._resolve_dom_image(html, entity, url=url)
                    
                    if dom_image and dom_score >= 3:
                        image_props["image"] = dom_image
                        image_props["mainImage"] = dom_image
                    elif dom_image and dom_score == 2:
                        image_props["candidateImage"] = dom_image

                    props = self._merge_properties(
                        self.property_enricher.enrich(entity, "Place", text),
                        page_props,
                        image_props,
                    )

                    desc = page_props.get("description", "")

                    classified_entities.append(
                        self._build_output_entity(
                            entity=entity,
                            label="Place",
                            score=0.5,
                            props=props,
                            short_description=desc[:180] if desc else "",
                            long_description=desc,
                            wikidata_id=None,
                            html=html,
                            text=text,
                            url=url,
                        )
                    )
                    print("\n=== TRAS _build_output_entity ===")
                    if classified_entities:
                        print(classified_entities[0])
            else:
                for e in llm_entities:
                    entity = self.clean_entity_edges(e.get("entity", ""))

                    if not entity or self.is_low_value_entity(entity, text):
                        continue

                    label = e.get("class", "Place")
                    score = e.get("score", 0.8)

                    base_props = self.property_enricher.enrich(entity, label, text)
                    page_props = self.tourism_property_extractor.extract(
                        html=html,
                        text=text,
                        url=url,
                        entity=entity,
                    ) or {}

                    try:
                        image_props = self.image_enricher.enrich(
                            entity=entity,
                            text=text,
                            html=html,
                        ) or {}
                    except Exception:
                        image_props = {}

                    dom_image, dom_score = self._resolve_dom_image(html, entity, url=url)
                    
                    if dom_image and dom_score >= 3:
                        image_props["image"] = dom_image
                        image_props["mainImage"] = dom_image
                    elif dom_image and dom_score == 2:
                        image_props["candidateImage"] = dom_image
                    

                    wikidata_props = {}
                    wikidata_id = None

                    try:
                        link = self.wikidata_linker.link(entity)
                        if isinstance(link, dict):
                            wikidata_id = link.get("id")
                        elif isinstance(link, str):
                            wikidata_id = link

                        if wikidata_id:
                            wikidata_props = self.wikidata_linker.get_entity_data(wikidata_id) or {}
                    except Exception:
                        wikidata_props = {}

                    props = self._merge_properties(
                        base_props,
                        page_props,
                        image_props,
                        wikidata_props,
                    )

                    short_description = e.get("short_description", "") or page_props.get("description", "")[:180]
                    long_description = e.get("long_description", "") or page_props.get("description", "")

                    classified_entities.append(
                        self._build_output_entity(
                            entity=entity,
                            label=label,
                            score=score,
                            props=props,
                            short_description=short_description,
                            long_description=long_description,
                            wikidata_id=wikidata_id,
                            html=html,
                            text=text,
                            url=url,
                        )
                    )
                    print("\n=== TRAS _build_output_entity ===")
                    if classified_entities:
                        print(classified_entities[0])

            cleaned_classified = []
            seen_classified = set()

            for item in classified_entities:
                entity_name = self.clean_entity_edges(item.get("entity", ""))
                if not entity_name:
                    continue

                if self.is_low_value_entity(entity_name, text):
                    continue

                key = entity_name.lower().strip()
                if key in seen_classified:
                    continue

                item["entity"] = entity_name
                item["entity_name"] = entity_name
                item["label"] = item.get("label") or entity_name
                item["name"] = item.get("name") or entity_name
                item["properties"] = self._normalize_final_image_props(item.get("properties", {}))

                if "image" not in item:
                    item["image"] = self._safe_string(item["properties"].get("image"))

                if "mainImage" not in item:
                    item["mainImage"] = self._safe_string(item["properties"].get("mainImage"))

                if "verisimilitude_score" not in item:
                    item["verisimilitude_score"] = item.get("score", 0.0)

                if "address" not in item:
                    item["address"] = self._safe_string(item["properties"].get("address"))

                if "phone" not in item:
                    item["phone"] = self._safe_string(
                        item["properties"].get("telephone") or item["properties"].get("phone")
                    )

                if "email" not in item:
                    extracted_email = (
                        self._safe_string(item["properties"].get("email"))
                        or self._safe_string(item["properties"].get("correo"))
                        or self._extract_email_from_html(html)
                    )
                    item["email"] = extracted_email if self._looks_like_email(extracted_email) else ""

                if "coordinates" not in item:
                    item["coordinates"] = self._build_coordinates(item["properties"])

                    print("\n=== TRAS _build_output_entity ===")
                    if classified_entities:
                        print(classified_entities[0])

                cleaned_classified.append(item)
                seen_classified.add(key)

            cleaned_classified = self.page_entity_resolver.resolve(cleaned_classified)
            print("\n=== TRAS PageEntityResolver ===")
            if cleaned_classified:
                print(cleaned_classified[0])

            classified_entities = cleaned_classified

            if not classified_entities:
                continue

            classified_entities = self.ranker.rank(classified_entities, text)
            classified_entities = self.clusterer.merge_clusters(classified_entities)

            self.global_memory.update(classified_entities)
            global_counts = self.global_memory.get_counts()

            for e in classified_entities:
                recomputed_score = self.entity_scorer.compute_importance(e, text, global_counts)
                e["score"] = recomputed_score
                e["verisimilitude_score"] = recomputed_score

            classified_entities = sorted(
                classified_entities,
                key=lambda x: x["score"],
                reverse=True,
            )

            relations = self.relation_extractor.extract(text)
            relations = self.sanitize_relations(relations)
            self.graph_builder.add_relations(relations)

            results.append(
                {
                    "text": text,
                    "url": url,
                    "entities": classified_entities,
                    "relations": relations,
                }
            )

            print("Relaciones:", relations)

        return results

    def _is_wikimedia_url(self, url):
        if not url:
            return False

        low = str(url).lower()
        return (
            "wikimedia.org" in low
            or "wikipedia.org" in low
            or "wikidata.org" in low
            or "commons.wikimedia.org" in low
        )

    def has_entity_signal(self, text: str) -> bool:
        t = (text or "").strip()
        if not t:
            return False

        patterns = [
            r"\b\d{9}\b",
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            r"\b(calle|plaza|avenida|avda|camino|carretera)\b",
            r"\b(museo|hotel|restaurante|iglesia|monumento|evento|festival|mercado|ruta|barrio)\b",
        ]

        if any(re.search(p, t, re.IGNORECASE) for p in patterns):
            return True

        words = t.split()
        if len(words) >= 2 and any(w[:1].isupper() for w in words):
            return True

        return False