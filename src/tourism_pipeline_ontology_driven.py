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
from src.block_quality_scorer import BlockQualityScorer
from src.entity_evidence_builder import EntityEvidenceBuilder
from src.ontology_reasoner import OntologyReasoner

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
        self.block_quality_scorer = BlockQualityScorer()
        self.entity_evidence_builder = EntityEvidenceBuilder()
        self.ontology_reasoner = OntologyReasoner(self.ontology_index)


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

    def is_operational_info_block(self, text):
        t = (text or "").lower()

        signals = [
            "de lunes a domingo",
            "de lunes a viernes",
            "sábados, domingos y festivos",
            "sabados, domingos y festivos",
            "horario",
            "horario especial",
            "oficina permanecerá cerrada",
            "la oficina permanecerá cerrada",
            "localización:",
            "localizacion:",
            "09:30",
            "14:30",
            "15:30",
            "18:30",
        ]

        hits = sum(1 for s in signals if s in t)
        return hits >= 3

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


        candidate = props.get("candidateImage")

        if candidate:
            candidate = self._normalize_image_url(candidate)
            if not candidate or self._is_wikimedia_url(candidate):
                props.pop("candidateImage", None)
            else:
                props["candidateImage"] = candidate
        else:
            props.pop("candidateImage", None)

        candidate = props.get("candidateImage")
        if candidate:
            candidate = self._normalize_image_url(candidate)
            if not candidate or self._is_wikimedia_url(candidate):
                props.pop("candidateImage", None)
            else:
                props["candidateImage"] = candidate
        else:
            props.pop("candidateImage", None) 

        return props

    def _resolve_dom_image(self, html, entity, url="", block_text=""):

        """
        Devuelve (image_url, score)
        """
        if self._is_bad_visual_asset(url):
            return"",0
        if self._is_bad_visual_asset(url):
            return"",0
        

        try:
            if hasattr(self.dom_image_resolver, "resolve_with_score"):
                return self.dom_image_resolver.resolve_with_score(
                    html=html,
                    entity_name=entity,
                    base_url=url,
                    block_text=block_text,
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
                    block_text=block_text,
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
    
    def _is_bad_visual_asset(self, url: str) -> bool:
        if not url:
            return True

        u = url.lower()

        bad_patterns = [
            "logo", "icon", "iconos", "svg", "sprite", "banner",
            "placeholder", "avatar", "header", "footer",
            "feeling", "negativo", "positivo",
            "share", "social", "separator", "separador"
        ]

        if url.lower().endswith(".svg"):
            return"",0

        return any(p in u for p in bad_patterns)
         
    


    
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

        if lng is None:
            lng = self._safe_float(props.get("lon"))

        if lat is None and isinstance(props.get("coordinates"), dict):
            lat = self._safe_float(props["coordinates"].get("lat"))

        if lng is None and isinstance(props.get("coordinates"), dict):
            lng = self._safe_float(
                props["coordinates"].get("lng") or props["coordinates"].get("lon")
            )

        if lat is not None and not (-90 <= lat <= 90):
            lat = None

        if lng is not None and not (-180 <= lng <= 180):
            lng = None

        return {
            "lat": lat,
            "lng": lng
        }    
       


    def _safe_entity_contact(self, props: dict, key: str) -> str:
        value = (props or {}).get(key)
        if value is None:
            return ""
        return str(value).strip()

    def _safe_entity_image(self, props: dict) -> str:
        generic_fragments = [
            "el-flamenco-bloque-2.jpg",
        ]
        for key in ("mainImage", "image", "candidateImage"):
            value = (props or {}).get(key)
            if not value:
                continue
            value = str(value).strip()
            if not value:
                continue
            if any(fragment in value for fragment in generic_fragments):
                continue
            return value
        return ""

    def _should_skip_partial_entity(self, current_name: str, all_entities) -> bool:
        current_name = (current_name or "").strip().lower()
        if not current_name:
            return True

        for other in all_entities or []:
            other_name = self.clean_entity_edges(other.get("entity", "")).strip().lower()
            if not other_name or other_name == current_name:
                continue
            if current_name in other_name and len(other_name) > len(current_name):
                return True
        return False

    def _should_have_generic_geo(self, entity: dict) -> bool:
        entity_type = entity.get("class") or entity.get("type") or ""
        entity_type = str(entity_type).lower()

        geo_types = [
            "place",
            "location",
            "tourismdestination",
            "city",
            "municipality",
        ]

        return any(t in entity_type for t in geo_types)    

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
        entity_class = self._safe_string(label) or "Thing"

        wikidata_id = self.wikidata_linker.link(
            entity_name=self._safe_string(entity),
            entity_class=entity_class,
            short_description=self._safe_string(short_description),
            long_description=self._safe_string(long_description),
            source_url=self._safe_string(url),
        )

        short_description = self._safe_string(short_description)
        long_description = self._safe_string(long_description)

        props = props if isinstance(props, dict) else {}
        props = self._normalize_final_image_props(props)

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

        related_urls = props.get("relatedUrls", [])
        if isinstance(related_urls, str):
            related_urls = [self._safe_string(related_urls)] if self._safe_string(related_urls) else []
        elif isinstance(related_urls, list):
            related_urls = [self._safe_string(x) for x in related_urls if self._safe_string(x)]
        else:
            related_urls = []

        final_image = self._safe_entity_image(props)
        final_address = self._safe_entity_contact(props, "address")
        final_phone = (
            self._safe_entity_contact(props, "telephone")
            or self._safe_entity_contact(props, "phone")
        )
        final_email = email
        final_coordinates = self._build_coordinates(props)

        entity_types = [entity_class]

        if entity_class in {"Place", "TouristAttraction", "Landmark", "Location"}:
            if "Location" not in entity_types:
                entity_types.append("Location")

        print("\n=== BUILD OUTPUT ENTITY DEBUG ===")
        print("ENTITY:", entity)
        print("WIKIDATA_ID:", wikidata_id)
        print("PROPS LATITUDE:", props.get("latitude"))
        print("PROPS LONGITUDE:", props.get("longitude"))
        print("PROPS COORDINATES:", props.get("coordinates"))
        print("FINAL COORDS:", final_coordinates)
        print("PROPS IMAGE:", props.get("image"))
        print("PROPS MAINIMAGE:", props.get("mainImage"))
        print("PROPS CANDIDATE:", props.get("candidateImage"))

        return {
            "entity": self._safe_string(entity),
            "entity_name": self._safe_string(entity),
            "label": self._safe_string(entity),
            "name": self._safe_string(entity),
            "class": entity_class,
            "type": entity_types,
            "score": float(score) if score is not None else 0.0,
            "verisimilitude_score": float(score) if score is not None else 0.0,
            "sourceUrl": self._safe_string(url),
            "properties": props,
            "short_description": short_description,
            "long_description": long_description,
            "description": fallback_desc,
            "address": final_address,
            "phone": final_phone,
            "email": final_email,
            "coordinates": final_coordinates,
            "wikidata_id": wikidata_id or "",
            "image": final_image,
            "mainImage": final_image,
            "relatedUrls": related_urls,
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

    def is_low_value_entity(self, entity, text=""):
        e = (entity or "").strip()
        e_low = e.lower().strip()

        if not e:
            return True

        # demasiado corto
        if len(e) <= 2:
            return True

        # sufijos editoriales
        bad_suffixes = [
            " leer",
            " leer más",
            " leer mas",
            " ver más",
            " ver mas",
            " mostrar más",
            " mostrar mas",
        ]
        if any(e_low.endswith(s) for s in bad_suffixes):
            return True

        # prefijos o ruido editorial
        bad_prefixes = [
            "localización",
            "localizacion",
            "horario",
            "oficina",
        ]
        if any(e_low.startswith(p) for p in bad_prefixes):
            return True

        # entidades demasiado genéricas
        bad_exact = {
            "leer",
            "evento",
            "ruta",
            "mercado",
            "música",
            "otros",
            "teatro",
            "deportes",
            "cultural",
            "actividades",
            "familia",
            "semana santa",
            "jueves santo",
            "viernes santo",
            "sábado santo",
            "sabado santo",
        }

        # ojo: aquí puedes quitar semana santa / jueves santo si en otras urls sí te interesan
        if e_low in bad_exact:
            return True

        # patrones tipo abreviaturas o trozos rotos
        if re.fullmatch(r"[A-ZÁÉÍÓÚÑ]\s+[A-ZÁÉÍÓÚÑ](\s+[A-ZÁÉÍÓÚÑ])?", e):
            return True

        # ruido de navegación/listado
        noisy_terms = [
            "leer más",
            "leer mas",
            "mostrar más",
            "mostrar mas",
            "next",
            "localización",
            "localizacion",
            "horario especial",
            "de lunes a domingo",
            "de lunes a viernes",
            "sábados, domingos y festivos",
            "sabados, domingos y festivos",
        ]
        joined = f"{e_low} {(text or '').lower()}"
        if any(t in joined for t in noisy_terms) and len(e.split()) <= 3:
            return True

        # trozos truncados muy típicos
        if e_low in {
            "sevilla leer",
            "guadalquivir leer",
            "alamillo leer",
            "parque de maría",
            "localización edificio",
            "localizacion edificio",
            "localización edificio laredo",
            "localizacion edificio laredo",
        }:
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
        local_image_keys = {"image", "mainImage", "additionalImages", "candidateImage"}
        local_images = []
        wikidata_image = None

        for props in prop_dicts:
            if not isinstance(props, dict) or not props:
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
                        local_images.extend([v for v in value if isinstance(v, str) and v.strip()])
                    elif isinstance(value, str) and value.strip():
                        local_images.append(value)
                    continue

                if key not in merged:
                    merged[key] = value
                    continue

                old_value = merged[key]

                if old_value == value:
                    continue

                if isinstance(old_value, list):
                    existing = old_value[:]
                else:
                    existing = [old_value]

                if isinstance(value, list):
                    incoming = value
                else:
                    incoming = [value]

                for item in incoming:
                    if item is None or item == "":
                        continue
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
                # Solo convertir a string si son valores simples
                if all(isinstance(v, (str, int, float, bool)) for v in value):
                    merged[key] = " | ".join(str(v) for v in value if v is not None and v != "")
                else:
                    # Si vinieran estructuras complejas, mejor conservar la lista
                    merged[key] = value

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

            if self.is_calendar_or_listing_block(text):
                continue

            if self.is_operational_info_block(text):
                continue

            print("\n--- TEXTO BLOQUE ---")
            print(text[:120])

            entities = []

            if self.is_contact_card_block(text):
                primary = self.extract_primary_entity_from_contact_block(text)
                if primary:
                    entities.append(primary)

            try:
                block_quality = self.block_quality_scorer.evaluate(text, html=html)
                if block_quality["decision"] == "discard" and not self.has_entity_signal(text):
                    continue
            except Exception:
                block_quality = {"score": 0.5, "decision": "keep"}

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
                llm_entities = self.llm_supervisor.analyze_entities(entities, text) or []
            except Exception:
                llm_entities = []

            print("\n=== DEBUG llm_entities ===")
            for i, item in enumerate(llm_entities):
                print(i, type(item), item)

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
                            url=url,
                        ) or {}
                    except Exception:
                        image_props = {}

                    dom_image, dom_score = self._resolve_dom_image(
                        html,
                        entity,
                        url=url,
                        block_text=text
                    )

                    if dom_image and dom_score >= 2:
                        image_props["image"] = dom_image
                        image_props["mainImage"] = dom_image
                    elif dom_image and dom_score == 1:
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
                        self.property_enricher.enrich(entity, "Place", text),
                        page_props,
                        image_props,
                        wikidata_props,
                    )

                    desc = page_props.get("description", "")

                    built_entity = self._build_output_entity(
                        entity=entity,
                        label="Place",
                        score=0.5,
                        props=props,
                        short_description=desc[:180] if desc else "",
                        long_description=desc,
                        wikidata_id=wikidata_id,
                        text=text,
                        url=url,
                    )

                    evidence = self.entity_evidence_builder.evaluate(
                        built_entity,
                        block_score=block_quality["score"]
                    )

                    built_entity["evidenceScore"] = evidence["evidenceScore"]
                    built_entity["evidenceFlags"] = evidence["evidenceFlags"]
                    built_entity["evidenceDecision"] = evidence["evidenceDecision"]

                    if evidence["evidenceDecision"] != "discard":
                        if evidence["evidenceDecision"] == "review":
                            built_entity["needsReview"] = True
                        classified_entities.append(built_entity)

                    print("\n=== TRAS _build_output_entity ===")
                    print(built_entity)

            else:
            
                for e in llm_entities:
                    if isinstance(e, dict):
                        entity = self.clean_entity_edges(
                            e.get("entity") or e.get("name") or e.get("label") or ""
                        )
                        label = e.get("class", "Place")
                        score = e.get("score", 0.8)
                        short_description = e.get("short_description", "")
                        long_description = e.get("long_description", "")
                    elif isinstance(e, str):
                        entity = self.clean_entity_edges(e)
                        label = "Place"
                        score = 0.8
                        short_description = ""
                        long_description = ""
                    else:
                        continue

                    if not entity or self.is_low_value_entity(entity, text):
                        continue

                    print("\n=== DEBUG ENTITY PIPELINE ===")
                    print("entity:", entity, type(entity))
                    print("label:", label, type(label))
                    print("score:", score, type(score))

                    try:
                        print("-> property_enricher.enrich")
                        base_props = self.property_enricher.enrich(entity, label, text)
                        print("OK property_enricher.enrich:", type(base_props), base_props)
                    except Exception as ex:
                        print("❌ ERROR en property_enricher.enrich:", repr(ex))
                        raise

                    try:
                        print("-> tourism_property_extractor.extract")
                        page_props = self.tourism_property_extractor.extract(
                            html=html,
                            text=text,
                            url=url,
                            entity=entity,
                        ) or {}
                        print("OK tourism_property_extractor.extract:", type(page_props), page_props)
                    except Exception as ex:
                        print("❌ ERROR en tourism_property_extractor.extract:", repr(ex))
                        raise

                    try:
                        print("-> image_enricher.enrich")
                        image_props = self.image_enricher.enrich(
                            entity=entity,
                            text=text,
                            html=html,
                            url=url,
                        ) or {}
                        print("OK image_enricher.enrich:", type(image_props), image_props)
                    except Exception as ex:
                        print("❌ ERROR en image_enricher.enrich:", repr(ex))
                        image_props = {}

                    try:
                        print("-> _resolve_dom_image")
                        dom_image, dom_score = self._resolve_dom_image(
                            html,
                            entity,
                            url=url,
                            block_text=text
                        )
                        print("OK _resolve_dom_image:", dom_image, dom_score)
                    except Exception as ex:
                        print("❌ ERROR en _resolve_dom_image:", repr(ex))
                        dom_image, dom_score = None, 0

                    if dom_image and dom_score >= 2:
                        image_props["image"] = dom_image
                        image_props["mainImage"] = dom_image
                    elif dom_image and dom_score == 1:
                        image_props["candidateImage"] = dom_image

                    wikidata_props = {}
                    wikidata_id = None

                    try:
                        print("-> wikidata_linker.link")
                        link = self.wikidata_linker.link(entity)
                        print("OK wikidata_linker.link:", type(link), link)

                        if isinstance(link, dict):
                            wikidata_id = link.get("id")
                        elif isinstance(link, str):
                            wikidata_id = link

                        if wikidata_id:
                            print("-> wikidata_linker.get_entity_data")
                            wikidata_props = self.wikidata_linker.get_entity_data(wikidata_id) or {}
                            print("OK wikidata_linker.get_entity_data:", type(wikidata_props), wikidata_props)
                    except Exception as ex:
                        print("❌ ERROR en wikidata:", repr(ex))
                        wikidata_props = {}

                    try:
                        print("-> _merge_properties")
                        props = self._merge_properties(
                            base_props,
                            page_props,
                            image_props,
                            wikidata_props,
                        )
                        print("OK _merge_properties:", type(props), props)
                    except Exception as ex:
                        print("❌ ERROR en _merge_properties:", repr(ex))
                        raise

                    if not short_description:
                        short_description = page_props.get("description", "")[:180]
                    if not long_description:
                        long_description = page_props.get("description", "")

                    try:
                        print("-> _build_output_entity")
                        built_entity = self._build_output_entity(
                            entity=entity,
                            label=label,
                            score=score,
                            props=props,
                            short_description=short_description,
                            long_description=long_description,
                            wikidata_id=wikidata_id,
                            text=text,
                            url=url,
                        )
                        print("OK _build_output_entity")
                    except Exception as ex:
                        print("❌ ERROR en _build_output_entity:", repr(ex))
                        raise

                    evidence = self.entity_evidence_builder.evaluate(
                        built_entity,
                        block_score=block_quality["score"]
                    )

                    built_entity["evidenceScore"] = evidence["evidenceScore"]
                    built_entity["evidenceFlags"] = evidence["evidenceFlags"]
                    built_entity["evidenceDecision"] = evidence["evidenceDecision"]

                    if evidence["evidenceDecision"] != "discard":
                        if evidence["evidenceDecision"] == "review":
                            built_entity["needsReview"] = True
                        classified_entities.append(built_entity)

                    print("\n=== TRAS _build_output_entity ===")
                    print(built_entity)    
                
            cleaned_classified = []
            seen_classified = set()

            print("\n=== DEBUG classified_entities BEFORE CLEAN ===")
            for i, dbg_item in enumerate(classified_entities):
                if isinstance(dbg_item, dict):
                    print(i, "DICT", dbg_item.get("entity"))
                else:
                    print(i, type(dbg_item), dbg_item)

            for item in classified_entities:
                if isinstance(item, str):
                    item = {
                        "entity": item,
                        "entity_name": item,
                        "label": item,
                        "name": item,
                        "class": "Thing",
                        "type": ["Thing"],
                        "score": 0.5,
                        "verisimilitude_score": 0.5,
                        "sourceUrl": url,
                        "properties": {},
                        "short_description": "",
                        "long_description": "",
                        "description": "",
                        "address": "",
                        "phone": "",
                        "email": "",
                        "coordinates": {"lat": None, "lng": None},
                        "wikidata_id": "",
                        "relatedUrls": [],
                        "url": "",
                    }

                if not isinstance(item, dict):
                    continue

                entity_name = self.clean_entity_edges(item.get("entity", ""))
                if not entity_name:
                    continue

                if self.is_low_value_entity(entity_name, text):
                    continue

                key = entity_name.lower().strip()
                if key in seen_classified:
                    continue

                skip_partial = False
                for other in classified_entities:
                    if isinstance(other, str):
                        other_name = self.clean_entity_edges(other)
                    elif isinstance(other, dict):
                        other_name = self.clean_entity_edges(other.get("entity", ""))
                    else:
                        continue

                    if not other_name:
                        continue

                    current_name = entity_name.lower().strip()
                    other_name_l = other_name.lower().strip()

                    if current_name != other_name_l and current_name and current_name in other_name_l:
                        if len(other_name_l) > len(current_name):
                            skip_partial = True
                            break

                if skip_partial:
                    continue

                item["entity"] = entity_name
                item["entity_name"] = entity_name
                item["label"] = item.get("label") or entity_name
                item["name"] = item.get("name") or entity_name

                if not isinstance(item.get("properties"), dict):
                    item["properties"] = {}

                item["properties"] = self._normalize_final_image_props(item.get("properties", {}))

                if "image" not in item or not item.get("image"):
                    item["image"] = self._safe_entity_image(item.get("properties", {}))

                if "mainImage" not in item or not item.get("mainImage"):
                    item["mainImage"] = item.get("image", "")

                if "verisimilitude_score" not in item:
                    item["verisimilitude_score"] = item.get("score", 0.0)

                if "address" not in item or not item.get("address"):
                    item["address"] = self._safe_entity_contact(item.get("properties", {}), "address")

                if "phone" not in item or not item.get("phone"):
                    item["phone"] = (
                        self._safe_entity_contact(item.get("properties", {}), "telephone")
                        or self._safe_entity_contact(item.get("properties", {}), "phone")
                    )

                if "email" not in item or not item.get("email"):
                    extracted_email = (
                        self._safe_string(item["properties"].get("email"))
                        or self._safe_string(item["properties"].get("correo"))
                    )
                    item["email"] = extracted_email if self._looks_like_email(extracted_email) else ""

                if "coordinates" not in item or not item.get("coordinates"):
                    item["coordinates"] = self._build_coordinates(item.get("properties", {}))

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
    def is_calendar_or_listing_block(self, text: str) -> bool:
        t = normalize_text(text)

        bad_signals = [
            "fecha inicio",
            "fecha fin",
            "limpiar fechas",
            "mostrar categorías",
            "ocultar categorías",
            "estas viendo todos los planes",
            "sin filtros",
            "next evento",
            "actividades en familia",
            "evento en la calle",
            "tradición religiosa",
            "visita guiada",
        ]

        if any(x in t for x in bad_signals):
            return True

        # días/meses repetidos tipo calendario
        if re.search(r"\b(l m x j v s d)\b", t):
            return True

        if re.search(r"\b1 2 3 4 5 6 7 8 9 10 11 12\b", t):
            return True

        # bloque muy largo con demasiadas categorías cortas
        words = t.split()
        short_tokens = sum(1 for w in words if len(w) <= 3)
        if len(words) > 20 and short_tokens > len(words) * 0.45:
            return True

        return False