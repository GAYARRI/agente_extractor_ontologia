from __future__ import annotations
from entity_processing.page_classifier import classify_page
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text or "")
        if not unicodedata.combining(ch)
    )


def normalize_entity_text(text: str) -> str:
    text = text or ""
    text = text.strip()
    text = re.sub(r"^\d+[\)_\-.]*\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n,.;:|/-–—•·")


def canonical_entity_key(text: str) -> str:
    text = normalize_entity_text(text).lower()
    return _strip_accents(text)


class EntityFilter:
    """
    Filtro conservador para cortar candidatos débiles antes del matching semántico.

    Filosofía:
    - si parece navegación/editorial/contacto => reject
    - si el nombre es demasiado genérico => reject
    - si no tiene evidencia positiva suficiente => reject
    - si hay duda real => review, pero no keep directo
    """

    def __init__(self) -> None:
        self.ui_exact = {
            "leer más", "leer mas", "más info", "mas info", "ver más", "ver mas",
            "inicio", "home", "descubre", "historia", "detalles", "detalle",
            "actividad", "actividades", "servicios", "información", "informacion",
            "contacto", "mapa", "mapas", "cómo llegar", "como llegar",
        }
        self.generic_single_token_blocklist = {
            "bienal", "academias", "tablaos", "flamenco", "visitantes",
            "agenda", "planes", "museos", "monumentos", "ocio", "familia",
            "cultura", "rutas", "barrios", "compras", "gastronomia", "gastronomía",
        }
        self.generic_multiword_blocklist = {
            "tablaos flamencos", "academias de flamenco", "que hacer",
            "qué hacer", "ideas y planes", "durante tu estancia", "de compras",
            "comer y salir", "monumentos y museos", "puntos de informacion turistica",
            "puntos de información turística",
        }
        self.person_like_titles = {
            "la niña de los peines", "niña de los peines", "manolo caracol",
        }
        self.noise_contains = {
            "google analytics", "cookies", "política de cookies", "politica de cookies",
            "privacidad", "aviso legal", "copy link", "watch later", "share",
            "suscrito", "te has suscrito", "ir a página", "ir a pagina",
            "abrir en google maps", "sitio web ver", "maps abrir",
        }
        self.contact_tokens = {
            "teléfono", "telefono", "dirección", "direccion", "email", "correo",
            "whatsapp", "horario", "horarios", "reservas",
        }
        self.place_allowlist = {"sevilla", "triana"}
        self.instance_indicators = {
            "museo", "iglesia", "capilla", "basilica", "basílica", "catedral",
            "palacio", "alcazar", "alcázar", "teatro", "tablao", "parque",
            "jardín", "jardin", "plaza", "puente", "barrio", "hotel", "hostal",
            "restaurante", "bar", "mercado", "ayuntamiento", "estadio", "festival",
            "bienal", "centro", "fundación", "fundacion", "asociación", "asociacion",
        }

    def _slug_tokens(self, url: str) -> List[str]:
        try:
            path = urlparse(url or "").path.lower()
        except Exception:
            return []
        return [t for t in re.split(r"[^\wáéíóúñü]+", path) if t]

    def _normalize_context(self, context: str) -> str:
        return canonical_entity_key(context)

    def looks_like_ui_fragment(self, text: str) -> bool:
        t = canonical_entity_key(text)
        if not t:
            return True
        if t in self.ui_exact:
            return True
        if t in self.generic_multiword_blocklist:
            return True
        if re.fullmatch(r"\d+_?", t):
            return True
        if t.startswith(("01 ", "02 ", "03 ")):
            return True
        if any(x in t for x in self.noise_contains):
            return True
        return False

    def is_generic_entity(self, text: str) -> bool:
        t = canonical_entity_key(text)
        if not t:
            return True
        if t in self.generic_single_token_blocklist or t in self.generic_multiword_blocklist:
            return True
        words = t.split()
        if len(words) == 1 and t not in self.place_allowlist and t not in self.person_like_titles:
            return True
        if len(words) >= 2 and all(w.isalpha() for w in words):
            if words[-1].endswith("s") and t == t.lower() and t not in self.person_like_titles:
                return True
        return False

    def _positive_signals(self, entity: str, context: str, page_signals: Optional[Dict[str, Any]] = None) -> Tuple[int, List[str]]:
        score = 0
        reasons: List[str] = []
        name = normalize_entity_text(entity)
        key = canonical_entity_key(name)
        context_k = self._normalize_context(context)
        page_signals = page_signals or {}

        words = name.split()
        meaningful = [w for w in words if len(w) > 2]
        if len(meaningful) >= 2:
            score += 2
            reasons.append("multiword_name")

        if any(ind in key for ind in self.instance_indicators):
            score += 2
            reasons.append("instance_indicator")

        if any(tok in context_k for tok in [
            "visitar", "visita", "monumento", "museo", "iglesia", "festival",
            "patrimonio", "barrio", "plaza", "palacio", "alojamiento", "restaurante",
            "ubicado", "situado", "se encuentra", "dirección", "direccion",
        ]):
            score += 1
            reasons.append("supportive_context")

        slug_tokens = set(page_signals.get("slug_tokens") or [])
        name_tokens = {canonical_entity_key(x) for x in words if len(x) > 3}
        if slug_tokens and name_tokens.intersection(slug_tokens):
            score += 2
            reasons.append("url_affinity")

        h1 = canonical_entity_key(page_signals.get("h1") or "")
        title = canonical_entity_key(page_signals.get("title") or "")
        if key and h1 and (key in h1 or h1 in key):
            score += 2
            reasons.append("h1_match")
        if key and title and (key in title or title in key):
            score += 1
            reasons.append("title_match")

        return score, reasons

    def evaluate(
        self,
        entity: str,
        context: str = "",
        page_signals: Optional[Dict[str, Any]] = None,
        expected_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        entity = normalize_entity_text(entity)
        context_k = self._normalize_context(context)
        reasons: List[str] = []

        if not entity:
            return {"decision": "reject", "score": -10, "reasons": ["empty"]}

        if len(entity) < 3 or len(entity.split()) > 8:
            return {"decision": "reject", "score": -6, "reasons": ["bad_length"]}

        if self.looks_like_ui_fragment(entity):
            return {"decision": "reject", "score": -8, "reasons": ["ui_fragment"]}

        key = canonical_entity_key(entity)
        if any(x in key for x in ["wenn", "sie", "und", "les", "des", "comment", "arriver"]):
            return {"decision": "reject", "score": -8, "reasons": ["foreign_noise"]}

        if any(tok in context_k for tok in ["breadcrumb", "menu", "navegación", "navegacion"]):
            return {"decision": "reject", "score": -6, "reasons": ["navigation_context"]}

        if self.is_generic_entity(entity):
            reasons.append("generic_name")

        if len(entity.split()) == 1 and key not in self.place_allowlist:
            reasons.append("single_token")

        if any(tok in key for tok in self.contact_tokens):
            return {"decision": "reject", "score": -6, "reasons": ["contact_fragment"]}

        pos_score, pos_reasons = self._positive_signals(entity, context, page_signals)
        reasons.extend(pos_reasons)

        score = pos_score
        if "generic_name" in reasons:
            score -= 3
        if "single_token" in reasons:
            score -= 2

        if expected_type and canonical_entity_key(expected_type) in key:
            score += 1
            reasons.append("expected_type_lexical_hint")

        if score >= 3 and "generic_name" not in reasons:
            decision = "keep"
        elif score >= 2:
            decision = "review"
        else:
            decision = "reject"

        return {
            "decision": decision,
            "score": score,
            "reasons": sorted(set(reasons)),
        }

    def filter(
        self,
        entities: List[Dict[str, Any]],
        context_getter=None,
        page_signals: Optional[Dict[str, Any]] = None,
        expected_type: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        kept: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        for item in entities or []:
            if not isinstance(item, dict):
                continue
            name = (
                item.get("name") or item.get("entity_name") or item.get("entity") or item.get("label") or ""
            )
            context = context_getter(item) if callable(context_getter) else (item.get("context") or "")
            

        page_type = classify_page(
            url=item.get("url") or item.get("sourceUrl") or "",
            entity=item
        )

        audit = self.evaluate(
            name,
            context=context,
            page_signals=page_signals,
            expected_type=expected_type
        )

        # 🔥 NEW: stricter filtering for bad page types
        if page_type in {"listing_page", "category_page", "blog_page"}:
            if audit["decision"] != "keep":
                audit["decision"] = "reject"
                audit["reasons"].append(f"rejected_by_page_type:{page_type}")

            if len(name.split()) > 7:
                audit["decision"] = "reject"
                audit["reasons"].append("too_long_for_listing")

            if any(tok in name.lower() for tok in ["lugares", "categorías", "planes", "que ver", "qué ver"]):
                audit["decision"] = "reject"
                audit["reasons"].append("category_noise")


            enriched = dict(item)
            enriched["filter_audit"] = audit
            if audit["decision"] == "reject":
                rejected.append(enriched)
            else:
                kept.append(enriched)
        return kept, rejected
