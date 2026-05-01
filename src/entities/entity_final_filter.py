from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Tuple


class EntityFinalFilter:
    """
    Filtro final conservador para entidades turísticas.

    Objetivo:
    - dejar pasar entidades turísticas plausibles y limpias
    - bloquear fragmentos narrativos, ruido UI y nombres contaminados
    - no matar entidades válidas por exceso de agresividad
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

        self.generic_names = {
            "mapas",
            "vista",
            "aquí",
            "aqui",
            "suscríbete",
            "suscribete",
            "apúntate",
            "apuntate",
            "preguntas frecuentes",
            "qué ver",
            "que ver",
            "qué hacer",
            "que hacer",
            "paseos",
            "experiencias",
            "agenda",
            "disfruta",
            "descubre",
            "ven",
            "profesionales",
            "programa",
            "viajar",
            "locales",
            "mercado",
            "plaza",
            "parque",
            "castillo",
            "además",
            "ademas",
        }

        self.ui_patterns = [
            r"\bir al contenido\b",
            r"\breserva tu actividad\b",
            r"\btodos los derechos reservados\b",
            r"\baccesibilidad\b",
            r"\bgu[ií]as convention bureau\b",
            r"\b[aá]rea profesional\b",
            r"\bver m[aá]s\b",
            r"\bleer m[aá]s\b",
            r"\bmostrar m[aá]s\b",
            r"\bgoogle maps\b",
            r"\bcopiar direcci[oó]n\b",
            r"\bcontacto\b",
            r"\bmapas\b",
        ]

        self.phrase_markers = {
            "es",
            "son",
            "fue",
            "fueron",
            "ser",
            "comenzaremos",
            "comenzará",
            "comenzara",
            "visitaremos",
            "llegaremos",
            "permite",
            "permiten",
            "ofrece",
            "ofrecen",
            "combina",
            "combinan",
            "disfruta",
            "disfrutar",
            "vivir",
            "tiene",
            "tienen",
            "ocurre",
            "ocurren",
            "puede",
            "pueden",
            "hay",
            "incluye",
            "incluyen",
            "data",
        }

        self.trailing_noise = {
            "también",
            "tambien",
            "comenzaremos",
            "comenzará",
            "comenzara",
            "pago recomendado",
            "ver",
            "más",
            "mas",
            "monumento",
            "monumentos",
            "espacios",
            "museo",
            "museos",
            "lugares",
            "lugar",
            "preguntas",
            "informacion",
            "información",
            "reserva",
            "reservar",
            "contacto",
            "horarios",
            "tarifas",
            "precios",
            "si",
        }

        self.leading_noise = {
            "actividad",
            "agenda",
            "programa",
            "experiencias",
            "visita guiada",
            "ir al contenido",
            "reserva tu actividad",
            "por supuesto",
            "también",
            "tambien",
            "además",
            "ademas",
        }

        self.instance_terms = {
            "ayuntamiento",
            "catedral",
            "iglesia",
            "basílica",
            "basilica",
            "capilla",
            "monasterio",
            "convento",
            "castillo",
            "alcázar",
            "alcazar",
            "palacio",
            "museo",
            "mercado",
            "plaza",
            "parque",
            "teatro",
            "puente",
            "festival",
            "feria",
            "congreso",
            "camino",
            "ruta",
            "sendero",
            "hotel",
            "hostal",
            "albergue",
            "camping",
            "centro de interpretación",
            "centro de interpretacion",
            "centro de acogida",
            "jardines",
            "ciudadela",
            "frontón",
            "fronton",
            "baluarte",
        }

        self.strong_valid_types = {
            "townhall",
            "cathedral",
            "church",
            "chapel",
            "basilica",
            "castle",
            "alcazar",
            "palace",
            "museum",
            "square",
            "park",
            "garden",
            "route",
            "stadium",
            "event",
            "monument",
            "market",
            "touristattraction",
        }

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------

    def _norm(self, value: Any) -> str:
        value = "" if value is None else str(value)
        value = value.strip()
        value = re.sub(r"\s+", " ", value)
        return value

    def _norm_low(self, value: Any) -> str:
        return self._norm(value).lower()

    def _strip_accents(self, text: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )

    def _tokenize(self, text: str) -> List[str]:
        return [t for t in re.split(r"[^\wáéíóúñü]+", self._norm_low(text)) if t]

    def _short_type(self, value: Any) -> str:
        raw = self._norm(value)
        if not raw:
            return ""
        return raw.split("#")[-1].split("/")[-1].strip()

    def _entity_name(self, entity: Dict[str, Any]) -> str:
        return self._norm(
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        )

    def _matches_detail_slug(self, entity: Dict[str, Any], cleaned_name: str) -> bool:
        url = self._norm_low(entity.get("sourceUrl") or entity.get("url") or "")
        if "/lugar/" not in url:
            return False

        slug = url.rstrip("/").split("/")[-1].replace("-", " ").replace("_", " ").strip()
        if not slug:
            return False

        clean_slug = self._strip_accents(slug).lower()
        clean_name = self._strip_accents(self._norm(cleaned_name)).lower()
        if not clean_name:
            return False

        return (
            clean_name == clean_slug
            or clean_name in clean_slug
            or clean_slug in clean_name
        )

    def _entity_class(self, entity: Dict[str, Any]) -> str:
        return self._short_type(entity.get("class") or entity.get("type") or "")

    def _description_text(self, entity: Dict[str, Any]) -> str:
        return self._norm(
            entity.get("description")
            or entity.get("long_description")
            or entity.get("longDescription")
            or entity.get("short_description")
            or entity.get("shortDescription")
            or ""
        )

    def _has_minimum_page_evidence(self, entity: Dict[str, Any]) -> bool:
        url = self._norm(entity.get("sourceUrl") or entity.get("url") or "")
        desc = self._description_text(entity)
        image = self._norm(entity.get("image") or entity.get("mainImage") or "")
        coords = entity.get("coordinates") if isinstance(entity.get("coordinates"), dict) else {}
        has_coords = coords.get("lat") is not None and coords.get("lng") is not None
        return bool(url or desc or image or has_coords)

    def _page_subject_text(self, entity: Dict[str, Any]) -> str:
        values = [
            entity.get("url") or "",
            entity.get("sourceUrl") or "",
            self._description_text(entity),
        ]
        return self._norm(" ".join(str(v or "") for v in values if v))

    def _page_type(self, entity: Dict[str, Any]) -> str:
        return self._norm_low(entity.get("pageType") or "")

    def _looks_like_infrastructure_page(self, entity: Dict[str, Any]) -> bool:
        page_subject = self._page_subject_text(entity)
        markers = (
            "transporte",
            "estacion de tren",
            "estacion de autobuses",
            "estacion de esqui",
            "aeropuerto",
            "puerto",
            "/esquiar/",
            "/transporte/",
        )
        return any(marker in page_subject for marker in markers)

    def _looks_like_transport_page(self, entity: Dict[str, Any]) -> bool:
        page_subject = self._page_subject_text(entity)
        markers = (
            "transporte",
            "como llegar",
            "en autobus",
            "en tren",
            "estacion de autobuses",
            "estacion de tren",
            "/transporte/",
        )
        return any(marker in page_subject for marker in markers)

    def _is_professional_page_noise(self, entity: Dict[str, Any], cleaned_name: str) -> bool:
        page_type = self._page_type(entity)
        page_subject = self._page_subject_text(entity)
        if page_type != "professional_page" and "/profesionales" not in page_subject:
            return False

        low_name = self._norm_low(cleaned_name)
        entity_class = self._entity_class(entity).lower()
        if entity_class and entity_class not in {"unknown", "organization", "service", "place", "location"}:
            return False

        noise_markers = (
            "profesionales",
            "turismo mice",
            "material",
            "descarga",
            "recursos",
            "sector",
            "estadistica",
            "estadística",
            "noticias del sector",
            "te puede interesar",
        )
        return any(marker in low_name for marker in noise_markers)

    def _is_contextual_transport_reference(self, entity: Dict[str, Any], cleaned_name: str) -> bool:
        if not self._looks_like_transport_page(entity):
            return False

        mention_role = self._norm_low(entity.get("mentionRole") or "")
        if mention_role not in {"standalone_candidate", "related_entity"}:
            return False

        entity_class = self._entity_class(entity).lower()
        if entity_class not in {
            "unknown",
            "museum",
            "cathedral",
            "church",
            "chapel",
            "monument",
            "palace",
            "historicalorculturalresource",
            "place",
            "location",
        }:
            return False

        low_name = self._norm_low(cleaned_name)
        desc = self._norm_low(self._description_text(entity))
        if not low_name or not desc or low_name not in desc:
            return False

        contextual_markers = (
            "a menos de",
            "a 5 km de",
            "a 10 minutos de",
            "a pocos minutos de",
            "cerca de",
            "del centro historico",
            "del centro histórico",
            "de la catedral",
            "del museo de",
        )
        return any(marker in desc for marker in contextual_markers)

    def _is_contextual_natural_mention_on_infrastructure_page(self, entity: Dict[str, Any], cleaned_name: str) -> bool:
        if not self._looks_like_infrastructure_page(entity):
            return False

        entity_class = self._entity_class(entity).lower()
        if entity_class not in {"garden", "naturalpark", "park", "route", "historicalorculturalresource", "place"}:
            return False

        desc = self._description_text(entity)
        low_desc = self._norm_low(desc)
        low_name = self._norm_low(cleaned_name)
        if not low_desc or not low_name or low_name not in low_desc:
            return False

        contextual_markers = (
            "junto al ",
            "junto a ",
            "cerca de ",
            "en la comarca",
            "en un entorno privilegiado",
            "situada en un entorno",
        )
        if not any(marker in low_desc for marker in contextual_markers):
            return False

        strong_subject_markers = (
            "estacion de esqui",
            "estacion de autobuses",
            "estacion de tren",
            "aeropuerto",
            "puerto",
        )
        page_subject = self._page_subject_text(entity)
        return any(marker in page_subject for marker in strong_subject_markers)

    def _looks_like_address_entity(self, entity: Dict[str, Any], cleaned_name: str) -> bool:
        low_name = self._norm_low(cleaned_name)
        if not low_name:
            return False

        if not any(low_name.startswith(prefix) for prefix in ("calle ", "plaza ", "avenida ", "avda ", "paseo ", "camino ")):
            return False

        desc = self._description_text(entity)
        if not desc:
            return False

        low_desc = self._norm_low(desc)
        low_name_with_comma = low_name + ","
        address_markers = (
            " s/n",
            " nº",
            " n°",
            " cp ",
            "codigo postal",
            "(",
        )
        has_postal_tail = low_name_with_comma in low_desc or any(marker in low_desc for marker in address_markers)
        if not has_postal_tail:
            return False

        entity_class = self._entity_class(entity).lower()
        if entity_class not in {"square", "park", "garden", "route", "place", "location", "historicalorculturalresource"}:
            return False

        page_subject = self._page_subject_text(entity)
        mismatch_markers = (
            "estacion",
            "aeropuerto",
            "hotel",
            "hostal",
            "parador",
            "balneario",
            "museo",
            "palacio",
            "castillo",
            "monasterio",
            "iglesia",
            "catedral",
        )
        if any(marker in page_subject for marker in mismatch_markers) and low_name not in page_subject.split(" s/n")[0]:
            return True

        return False

    def _has_subject_mismatch(self, entity: Dict[str, Any], cleaned_name: str) -> bool:
        low_name = self._norm_low(cleaned_name)
        desc = self._description_text(entity)
        if not low_name or not desc:
            return False

        low_desc = self._norm_low(desc)
        if low_name in low_desc:
            return False

        page_subject = self._page_subject_text(entity)
        if not page_subject:
            return False

        strong_subject_markers = (
            "estacion de ",
            "aeropuerto de ",
            "hotel ",
            "parador ",
            "museo ",
            "catedral de ",
            "palacio de ",
            "castillo de ",
        )
        return any(marker in page_subject for marker in strong_subject_markers)

    def _looks_like_route_editorial_reference(self, entity: Dict[str, Any]) -> bool:
        page_role = self._norm_low(entity.get("pageRole") or "")
        mention_role = self._norm_low(entity.get("mentionRole") or "")
        page_structure = self._norm_low(entity.get("pageStructure") or "")
        url = self._norm_low(entity.get("sourceUrl") or entity.get("url") or "")
        if page_role != "child" or mention_role != "standalone_candidate":
            return False
        if page_structure != "hierarchical" and "/ruta/" not in url and "/camino/" not in url:
            return False

        desc = self._norm_low(self._description_text(entity))
        if not desc:
            return False

        editorial_markers = (
            "consejos y recomendaciones",
            "te hemos propuesto",
            "si tienes mas dias",
            "si tienes más dias",
            "nos gustaria recomendarte",
            "nos gustaría recomendarte",
            "otros tres planes",
            "sin embargo",
        )
        return any(marker in desc for marker in editorial_markers)

    def _has_route_location_mismatch(self, entity: Dict[str, Any], cleaned_name: str) -> bool:
        page_role = self._norm_low(entity.get("pageRole") or "")
        mention_role = self._norm_low(entity.get("mentionRole") or "")
        page_structure = self._norm_low(entity.get("pageStructure") or "")
        url = self._norm_low(entity.get("sourceUrl") or entity.get("url") or "")
        if page_role != "child" or mention_role != "standalone_candidate":
            return False
        if page_structure != "hierarchical" and "/ruta/" not in url and "/camino/" not in url:
            return False

        match = re.search(r"\bde\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]+(?:\s+[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]+){0,2})$", cleaned_name)
        if not match:
            return False

        location_tail = self._strip_accents(match.group(1)).lower().strip()
        if not location_tail or len(location_tail) < 4:
            return False

        page_subject = self._strip_accents(self._page_subject_text(entity)).lower()
        if not page_subject:
            return False

        generic_tails = {
            "la barca",
            "la ribera",
            "la vieja",
            "la nueva",
            "santiago",
        }
        if location_tail in generic_tails:
            return False

        return location_tail not in page_subject

    # ------------------------------------------------------------------
    # Limpieza de nombres
    # ------------------------------------------------------------------

    def _clean_name_edges(self, text: str) -> str:
        value = self._norm(text)

        changed = True
        while changed and value:
            changed = False
            low = self._norm_low(value)

            for prefix in sorted(self.leading_noise, key=len, reverse=True):
                if low.startswith(prefix + " "):
                    value = self._norm(value[len(prefix):])
                    changed = True
                    break

            if changed:
                continue

            low = self._norm_low(value)
            for suffix in sorted(self.trailing_noise, key=len, reverse=True):
                if low.endswith(" " + suffix):
                    value = self._norm(value[: -len(suffix)])
                    changed = True
                    break
                if low == suffix:
                    value = ""
                    changed = True
                    break

        value = re.sub(r"\s+", " ", value).strip(" -|,;:")
        return value

    # ------------------------------------------------------------------
    # Señales
    # ------------------------------------------------------------------

    def _looks_like_ui_fragment(self, text: str) -> bool:
        low = self._norm_low(text)
        if not low:
            return True
        return any(re.search(p, low, flags=re.IGNORECASE) for p in self.ui_patterns)

    def _looks_like_phrase_fragment(self, text: str) -> bool:
        low = self._norm_low(text)
        tokens = self._tokenize(low)

        if not tokens:
            return True

        if re.search(r"\b(quién|quien|cuándo|cuando|cómo|como)\b", low):
            return True

        if len(tokens) >= 6:
            return True

        if len(tokens) >= 4 and any(t in self.phrase_markers for t in tokens):
            return True

        return False

    def _looks_like_foreign_noise(self, text: str) -> bool:
        low = self._norm_low(text)
        patterns = [
            r"\bmultitud de actividades\b",
            r"\bplanifica tu viaje\b",
            r"\bdescubre pamplona\b",
            r"\bmoverse por pamplona\b",
            r"\btodos los lugares\b",
            r"\bd[oó]nde alojarse\b",
            r"\bd[oó]nde comer\b",
            r"\bqu[eé] ver\b",
            r"\bqu[eé] hacer\b",
        ]
        return any(re.search(p, low, flags=re.IGNORECASE) for p in patterns)

    def _looks_like_generic_name(self, text: str) -> bool:
        low = self._norm_low(text)
        return low in self.generic_names

    def _looks_like_person_name(self, text: str) -> bool:
        """
        Señal débil. No implica rechazo.
        Solo sirve para no premiar demasiado ciertos nombres.
        """
        name = self._norm(text)
        parts = [p for p in re.split(r"\s+", name) if p]
        if len(parts) < 2 or len(parts) > 4:
            return False

        uppercase_like = 0
        for p in parts:
            if re.match(r"^[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü\-]+$", p):
                uppercase_like += 1

        return uppercase_like >= 2

    def _has_instance_signal(self, text: str) -> bool:
        low = self._norm_low(text)
        return any(term in low for term in self.instance_terms)

    def _name_quality_score(self, name: str, entity_class: str = "") -> float:
        clean = self._clean_name_edges(name)
        low = self._norm_low(clean)
        tokens = self._tokenize(clean)
        score = 0.0

        if clean:
            score += 1.0

        if len(tokens) >= 2:
            score += 1.0

        if len(tokens) >= 2 and len(tokens) <= 5:
            score += 1.0

        if self._has_instance_signal(clean):
            score += 2.0

        if entity_class and entity_class.lower() in self.strong_valid_types:
            score += 1.0

        if self._looks_like_person_name(clean):
            score += 0.25  # señal débil, no fuerte

        if self._looks_like_ui_fragment(clean):
            score -= 4.0

        if self._looks_like_foreign_noise(clean):
            score -= 4.0

        if self._looks_like_phrase_fragment(clean):
            score -= 4.0

        if self._looks_like_generic_name(clean):
            score -= 3.0

        return score

    # ------------------------------------------------------------------
    # Reglas finales
    # ------------------------------------------------------------------

    def _should_keep(self, entity: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        raw_name = self._entity_name(entity)
        cleaned_name = self._clean_name_edges(raw_name)
        entity_class = self._entity_class(entity)
        reasons: List[str] = []

        if not cleaned_name:
            reasons.append("empty_name_after_cleaning")
            return False, reasons, {"cleaned_name": cleaned_name}

        if not self._has_minimum_page_evidence(entity):
            reasons.append("missing_page_evidence")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._looks_like_ui_fragment(cleaned_name):
            reasons.append("ui_fragment")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._looks_like_foreign_noise(cleaned_name):
            reasons.append("foreign_noise")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._looks_like_phrase_fragment(cleaned_name):
            if not self._matches_detail_slug(entity, cleaned_name):
                reasons.append("phrase_fragment")
                return False, reasons, {"cleaned_name": cleaned_name}

        if self._looks_like_generic_name(cleaned_name):
            reasons.append("generic_name")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._is_professional_page_noise(entity, cleaned_name):
            reasons.append("professional_page_noise")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._looks_like_address_entity(entity, cleaned_name):
            reasons.append("address_like_promoted_entity")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._is_contextual_natural_mention_on_infrastructure_page(entity, cleaned_name):
            reasons.append("contextual_natural_mention_on_infrastructure_page")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._has_subject_mismatch(entity, cleaned_name) and not self._matches_detail_slug(entity, cleaned_name):
            reasons.append("subject_context_mismatch")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._is_contextual_transport_reference(entity, cleaned_name):
            reasons.append("transport_context_reference")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._looks_like_route_editorial_reference(entity):
            reasons.append("route_editorial_reference")
            return False, reasons, {"cleaned_name": cleaned_name}

        if self._has_route_location_mismatch(entity, cleaned_name):
            reasons.append("route_location_mismatch")
            return False, reasons, {"cleaned_name": cleaned_name}

        tokens = self._tokenize(cleaned_name)
        if len(tokens) == 1 and not self._has_instance_signal(cleaned_name):
            reasons.append("single_token_without_instance_signal")
            return False, reasons, {"cleaned_name": cleaned_name}

        score = self._name_quality_score(cleaned_name, entity_class=entity_class)

        strong_type = entity_class.lower() in self.strong_valid_types if entity_class else False
        strong_instance = self._has_instance_signal(cleaned_name)

        if score < 0:
            reasons.append("low_name_quality")
            return False, reasons, {"cleaned_name": cleaned_name, "quality_score": score}

        if not strong_type and not strong_instance and len(tokens) >= 4:
            reasons.append("long_name_without_strong_support")
            return False, reasons, {"cleaned_name": cleaned_name, "quality_score": score}

        return True, reasons, {"cleaned_name": cleaned_name, "quality_score": score}

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def filter(self, entities: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        kept: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for entity in entities or []:
            if not isinstance(entity, dict):
                continue

            item = dict(entity)
            keep, reasons, meta = self._should_keep(item)

            cleaned_name = meta.get("cleaned_name") or self._entity_name(item)
            if cleaned_name:
                item["name"] = cleaned_name
                item["entity_name"] = cleaned_name
                item["label"] = cleaned_name
                item["entity"] = cleaned_name

            audit = item.get("final_filter_audit") or {}
            if not isinstance(audit, dict):
                audit = {}

            audit["decision"] = "keep" if keep else "reject"
            audit["reasons"] = reasons
            audit["name"] = cleaned_name
            audit["primary_class"] = self._entity_class(item) or ""
            audit["quality_score"] = meta.get("quality_score")
            audit["url"] = item.get("sourceUrl") or item.get("url") or ""
            item["final_filter_audit"] = audit

            if keep:
                kept.append(item)
            else:
                item["discarded_by_final_filter"] = True
                rejected.append(item)

        if self.debug:
            print(f"[FINAL FILTER] kept={len(kept)} rejected={len(rejected)}")
            for sample in rejected[:10]:
                try:
                    print(
                        "[FINAL FILTER][REJECT]",
                        f"name={sample.get('name')!r}",
                        f"reasons={sample.get('final_filter_audit', {}).get('reasons', [])}",
                    )
                except Exception:
                    pass

        return kept, rejected
