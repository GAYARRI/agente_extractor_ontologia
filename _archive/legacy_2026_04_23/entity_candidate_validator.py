# -*- coding: utf-8 -*-
"""
entity_candidate_validator.py

Validation and sanitation layer for extracted entity candidates.

Purpose
-------
This module protects the pipeline from:
- malformed names coming from menus / category pages / repeated labels
- semantic drift in type assignment
- concatenated UI labels such as "Hotel Leyre Ver"
- false positives inherited from listing pages
- impossible name/type combinations

Typical use
-----------
candidate = validate_candidate(candidate, page_url=url)
if candidate is None:
    # drop candidate
else:
    # keep candidate

Expected candidate format
-------------------------
A dict-like object with at least:
{
    "name": "...",
    "types": ["Museum", "Location"],
    "url": "...",
    "image": "...",
    ...
}
"""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple


GENERIC_TYPES = {
    "Thing",
    "Unknown",
    "Location",
    "Place",
    "TourismResource",
}

# Words that often indicate category/list/menu pollution
NOISE_TOKENS = {
    "ver",
    "mas",
    "más",
    "lugares",
    "lugar",
    "tipo",
    "tipos",
    "categoria",
    "categorias",
    "categoría",
    "categorías",
    "hoteles",
    "hotel",
    "albergues",
    "albergue",
    "hostales",
    "hostal",
    "pensiones",
    "pension",
    "pensión",
    "restaurantes",
    "restaurante",
    "museos",
    "museo",
    "monumentos",
    "mercados",
    "excursiones",
    "excursion",
    "excursión",
    "actividades",
    "visitas",
    "guiadas",
    "senderismo",
    "cicloturismo",
    "paseos",
    "rutas",
    "espacios",
    "culturales",
    "familia",
    "familias",
    "turismo",
    "gastronomia",
    "gastronomía",
    "comer",
    "alojarse",
    "dormir",
    "hacer",
    "que",
    "qué",
    "todo",
    "todos",
    "donde",
    "dónde",
    "desde",
    "pamplona",
    "iruna",
    "iruña",
}

# Strong indicators that a whole surface form is probably noise
REJECT_EXACT_NORMALIZED = {
    "ver",
    "ver mas",
    "ver más",
    "lugares",
    "monumentos",
    "mercados",
    "museos",
    "restaurantes",
    "albergues",
    "hoteles",
    "que ver",
    "que hacer",
    "donde comer",
    "donde alojarse",
    "planifica tu viaje",
    "descubre pamplona",
    "cultura muy viva",
    "historia de la ciudad",
    "camino de santiago",
    "san fermin",
    "san fermín",
}

# Suffixes often appended by cards or category pages
TRIMMABLE_SUFFIXES = [
    r"\bver\b",
    r"\bver\s+m[aá]s\b",
    r"\bhoteles\b",
    r"\balbergues\b",
    r"\brestaurantes\b",
    r"\bmuseos\b",
    r"\bmercados\b",
    r"\bexcursiones\b",
    r"\bactividades\b",
    r"\bvisitas\b",
    r"\bguiadas\b",
]

# Name tokens that often indicate invalid extracted surfaces
BAD_NAME_PATTERNS = [
    r"\bver\b",
    r"\bver\s+m[aá]s\b",
    r"\btodos\s+los\s+lugares\b",
    r"\bqu[eé]\s+ver\b",
    r"\bqu[eé]\s+hacer\b",
    r"\bd[oó]nde\s+comer\b",
    r"\bd[oó]nde\s+alojarse\b",
    r"\bplanifica\s+tu\s+viaje\b",
    r"\bdescubre\s+pamplona\b",
    r"\bcategor[ií]as?\b",
]

# Strong lexical expectations by type
TYPE_LEXICAL_PREFERENCES = {
    "Museum": [r"\bmuseo\b", r"\bmuseoa\b"],
    "Cathedral": [r"\bcatedral\b"],
    "Church": [r"\biglesia\b", r"\bparroquia\b"],
    "Square": [r"\bplaza\b"],
    "TownHall": [r"\bayuntamiento\b"],
    "AccommodationEstablishment": [
        r"\bhotel\b",
        r"\bhostal\b",
        r"\bhostel\b",
        r"\balbergue\b",
        r"\bpensi[oó]n\b",
        r"\bpension\b",
        r"\bapartamento\b",
        r"\bcamping\b",
        r"\bcasa\s+rural\b",
    ],
    "Event": [
        r"\bfestival\b",
        r"\bferia\b",
        r"\bconcierto\b",
        r"\bexposici[oó]n\b",
        r"\bexposicion\b",
        r"\bjornada\b",
        r"\bvinofest\b",
    ],
    "FoodEstablishment": [
        r"\bcaf[eé]\b",
        r"\bbar\b",
        r"\brestaurante\b",
        r"\basador\b",
        r"\bsidrer[ií]a\b",
        r"\bmes[oó]n\b",
    ],
}

# Type/name mismatches that should almost always be rejected
TYPE_REJECTION_PATTERNS = {
    "Basilica": [
        r"\bparque\b",
        r"\bfluvial\b",
        r"\barena\b",
        r"\bfestival\b",
        r"\bhotel\b",
        r"\bhostel\b",
        r"\balbergue\b",
        r"\bmuseo\b",
        r"\bmercado\b",
        r"\bfront[oó]n\b",
        r"\bcicloturismo\b",
        r"\bsenderismo\b",
    ],
    "Cathedral": [
        r"\bhotel\b",
        r"\bhostel\b",
        r"\balbergue\b",
        r"\bhostal\b",
        r"\bpensi[oó]n\b",
        r"\bpension\b",
        r"\blibrer[ií]a\b",
        r"\bcaf[eé]\b",
        r"\bbar\b",
        r"\bfestival\b",
        r"\bmercado\b",
    ],
    "Castle": [
        r"\barena\b",
        r"\bfestival\b",
        r"\bvinofest\b",
        r"\bcaf[eé]\b",
        r"\bhotel\b",
        r"\bhostel\b",
        r"\balbergue\b",
        r"\bmercado\b",
        r"\bfront[oó]n\b",
        r"\bparque\b",
        r"\bfluvial\b",
    ],
    "TownHall": [
        r"\bhotel\b",
        r"\bhostel\b",
        r"\balbergue\b",
        r"\bhostal\b",
        r"\barena\b",
        r"\bfestival\b",
        r"\bcaf[eé]\b",
        r"\bbar\b",
        r"\bmercado\b",
    ],
    "Monument": [
        r"\bhotel\b",
        r"\bhostel\b",
        r"\balbergue\b",
        r"\bfestival\b",
        r"\bcaf[eé]\b",
        r"\bbar\b",
        r"\bturismo\s+de\s+salud\b",
    ],
}

# URLs that usually represent list/index pages rather than entity detail pages
LISTING_URL_PATTERNS = [
    r"/tipo-lugar/",
    r"/lugares/page/\d+",
    r"/category/",
    r"/eventos/page/\d+",
    r"/blog/page/\d+",
    r"/en/lugares/page/\d+",
]

# URLs that are broad section pages, not detail pages
SECTION_URL_PATTERNS = [
    r"/tipo-lugar/que-ver/?$",
    r"/tipo-lugar/que-hacer/?$",
    r"/tipo-lugar/donde-alojarse/?$",
    r"/planifica-tu-viaje/donde-comer/?$",
    r"/que-hacer/?$",
    r"/que-ver/?$",
    r"/donde-comer/?$",
    r"/donde-alojarse/?$",
    r"/descubre-pamplona/?$",
]


def validate_candidate(candidate: Dict[str, Any], page_url: str = "") -> Optional[Dict[str, Any]]:
    """
    Main entry point.

    Returns:
        - cleaned/validated candidate dict if accepted
        - None if candidate should be dropped
    """
    if not isinstance(candidate, dict):
        return None

    entity = deepcopy(candidate)

    raw_name = safe_str(entity.get("name"))
    if not raw_name:
        return None

    cleaned_name = clean_name(raw_name)
    if not cleaned_name:
        return None

    # Try salvage
    cleaned_name = salvage_name(cleaned_name)
    cleaned_name = clean_name(cleaned_name)
    if not cleaned_name:
        return None

    if is_exact_noise_name(cleaned_name):
        return None

    if is_malformed_name(cleaned_name):
        return None

    if page_url and is_listing_like_page(page_url):
        # On list/index pages we apply much stricter name acceptance
        if not looks_like_real_entity_name(cleaned_name):
            return None
        if has_listing_pollution(cleaned_name):
            return None

    types = normalize_types(entity.get("types"))
    types = remove_impossible_types(cleaned_name, types)

    # If type list becomes empty, keep only generic fallback
    if not types:
        types = ["Unknown", "Location"]

    # Additional sanity
    if should_reject_by_name_and_type(cleaned_name, types):
        return None

    # Reject some classic false positives even if they pass prior filters
    if is_probable_false_positive(cleaned_name, page_url=page_url, types=types):
        return None

    entity["name"] = cleaned_name
    entity["types"] = dedupe_preserve_order(types)
    entity["score"] = normalize_score(entity.get("score", 1.0))

    return entity


# ---------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------

def safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_score(value: Any) -> float:
    try:
        v = float(value)
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v
    except Exception:
        return 1.0


def dedupe_preserve_order(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )


def normalized_text(text: str) -> str:
    txt = strip_accents(safe_str(text)).lower()
    txt = re.sub(r"[^\w\s/-]", " ", txt, flags=re.UNICODE)
    txt = re.sub(r"[_\-/]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def title_case_soft(text: str) -> str:
    """
    Soft title casing that preserves short connectors.
    """
    if not text:
        return text

    lowers = {
        "de", "del", "la", "las", "el", "los", "y", "o", "a", "en", "al",
        "da", "do", "dos", "das"
    }

    parts = text.split()
    result = []
    for i, part in enumerate(parts):
        low = part.lower()
        if i > 0 and low in lowers:
            result.append(low)
        else:
            result.append(part[:1].upper() + part[1:])
    return " ".join(result)


# ---------------------------------------------------------------------
# Name cleaning / salvage
# ---------------------------------------------------------------------

def clean_name(name: str) -> str:
    text = safe_str(name)
    text = re.sub(r"\s+", " ", text).strip(" -|,;:/")
    text = re.sub(r"\bVer\s+m[aá]s\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bVer\b$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -|,;:/")

    # Remove duplicated punctuation / separators
    text = re.sub(r"\s*[|/]\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()

    return title_case_soft(text)


def salvage_name(name: str) -> str:
    """
    Tries to rescue a plausible entity surface from a polluted one.
    """
    text = safe_str(name)

    # Trim obvious suffixes
    for suffix_pattern in TRIMMABLE_SUFFIXES:
        text = re.sub(rf"(?:\s+{suffix_pattern})+$", "", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip(" -|,;:/")

    # Rescue known leading structures from polluted hotel/accommodation strings
    rescue_patterns = [
        # Example: "Museo Pablo Sarasate Museos" -> "Museo Pablo Sarasate"
        (r"^(Museo\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*){0,4})\b", 1),

        # Example: "Iglesia San Saturnino" or "Iglesia de San Nicolás"
        (r"^(Iglesia(?:\s+de)?\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*){0,5})\b", 1),

        # Example: "Parque de la Media Luna"
        (r"^(Parque\s+(?:de|del|de la|de los|de las)\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ][\wÁÉÍÓÚÑáéíóúñ\-]*){0,5})\b", 1),

        # Example: "Palacio de Congresos Baluarte Ver" -> "Palacio de Congresos Baluarte"
        (r"^(Palacio(?:\s+de\s+Congresos)?\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ][\wÁÉÍÓÚÑáéíóúñ\-]*){0,4})\b", 1),

        # Example: "Hotel Leyre Ver" -> "Hotel Leyre"
        (r"^(Hotel\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*){0,4})\b", 1),

        # Example: "Café Iruña"
        (r"^(Caf[eé]\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*){0,3})\b", 1),

        # Example: "Festival Ecozine"
        (r"^(Festival\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ\-]*){0,4})\b", 1),

        # Example: "Navarra Arena"
        (r"^(Navarra\s+Arena)\b", 1),

        # Example: "Ayuntamiento de Pamplona Plaza Consistorial"
        (r"^(Ayuntamiento\s+de\s+Pamplona(?:\s+Plaza\s+Consistorial)?)\b", 1),

        # Example: "Puente la Reina"
        (r"^(Puente\s+la\s+Reina)\b", 1),
    ]

    for pattern, group_num in rescue_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            rescued = match.group(group_num).strip(" -|,;:/")
            if rescued:
                return title_case_soft(rescued)

    return text


def is_exact_noise_name(name: str) -> bool:
    return normalized_text(name) in REJECT_EXACT_NORMALIZED


def is_malformed_name(name: str) -> bool:
    norm = normalized_text(name)
    if not norm:
        return True

    # Too short
    if len(norm) < 3:
        return True

    # Too many repeated generic category tokens
    tokens = norm.split()
    noise_count = sum(1 for tok in tokens if tok in NOISE_TOKENS)
    if len(tokens) >= 4 and noise_count >= max(2, len(tokens) // 2):
        return True

    # Excessively long names are usually concatenations
    if len(tokens) >= 7:
        return True

    # Bad patterns
    for pattern in BAD_NAME_PATTERNS:
        if re.search(pattern, norm, flags=re.IGNORECASE):
            return True

    # Looks like joined menu/category labels
    if re.search(
        r"\b(hoteles|albergues|museos|mercados|restaurantes|excursiones|actividades|visitas)\b.*\b(hoteles|albergues|museos|mercados|restaurantes|excursiones|actividades|visitas)\b",
        norm,
        flags=re.IGNORECASE,
    ):
        return True

    # Starts or ends with generic list/category token
    if tokens and (tokens[0] in NOISE_TOKENS or tokens[-1] in NOISE_TOKENS):
        return True

    return False


def has_listing_pollution(name: str) -> bool:
    norm = normalized_text(name)

    # Names with many generic list/category words
    tokens = norm.split()
    if not tokens:
        return True

    noise_count = sum(1 for tok in tokens if tok in NOISE_TOKENS)
    return noise_count >= 2


def looks_like_real_entity_name(name: str) -> bool:
    """
    Strict heuristic for accepting names on listing pages.
    """
    norm = normalized_text(name)
    tokens = norm.split()
    if not tokens:
        return False

    # Prefer 2-5 token names
    if len(tokens) > 5:
        return False

    # Reject mostly generic-token names
    content_tokens = [tok for tok in tokens if tok not in NOISE_TOKENS]
    if len(content_tokens) == 0:
        return False

    # Must contain at least one capitalized-looking real chunk in original form
    words = safe_str(name).split()
    capitalish = sum(1 for w in words if re.match(r"^[A-ZÁÉÍÓÚÑ]", w))
    if capitalish == 0:
        return False

    return True


# ---------------------------------------------------------------------
# Type normalization / sanity
# ---------------------------------------------------------------------

def normalize_types(types_value: Any) -> List[str]:
    if types_value is None:
        return []

    if isinstance(types_value, str):
        types = [types_value]
    elif isinstance(types_value, list):
        types = [safe_str(t) for t in types_value if safe_str(t)]
    else:
        return []

    # normalize spacing
    types = [re.sub(r"\s+", "", t) if " " not in t.strip() else t.strip() for t in types]
    types = [t for t in types if t]

    return dedupe_preserve_order(types)


def remove_impossible_types(name: str, types: List[str]) -> List[str]:
    """
    Removes types that strongly contradict the lexical content of the name.
    """
    if not types:
        return types

    clean_types: List[str] = []
    norm_name = normalized_text(name)

    for t in types:
        # Keep generic types for now
        if t in GENERIC_TYPES:
            clean_types.append(t)
            continue

        reject_patterns = TYPE_REJECTION_PATTERNS.get(t, [])
        rejected = any(re.search(pat, norm_name, flags=re.IGNORECASE) for pat in reject_patterns)
        if not rejected:
            clean_types.append(t)

    # If all specific types disappeared, keep Unknown
    if not clean_types:
        return ["Unknown", "Location"]

    # Rebuild with best lexical preference ordering
    preferred_specific = preferred_types_for_name(name)
    ordered: List[str] = []

    # Add preferred types first if present
    for pref in preferred_specific:
        if pref in clean_types and pref not in ordered:
            ordered.append(pref)

    # Then remaining specific
    for t in clean_types:
        if t not in ordered and t not in GENERIC_TYPES:
            ordered.append(t)

    # Then generic fallbacks
    if "Location" in types and "Location" not in ordered:
        ordered.append("Location")
    if "Unknown" in types and "Unknown" not in ordered and not any(t not in GENERIC_TYPES for t in ordered):
        ordered.insert(0, "Unknown")

    if not ordered:
        ordered = ["Unknown", "Location"]

    return ordered


def preferred_types_for_name(name: str) -> List[str]:
    norm_name = normalized_text(name)
    prefs: List[str] = []
    for type_name, patterns in TYPE_LEXICAL_PREFERENCES.items():
        if any(re.search(pat, norm_name, flags=re.IGNORECASE) for pat in patterns):
            prefs.append(type_name)

    # Some direct rules
    if re.search(r"\bfront[oó]n\b", norm_name, flags=re.IGNORECASE):
        # Better to remain unknown than drift to religious/historic classes
        prefs.append("Unknown")

    if re.search(r"\bparque\b", norm_name, flags=re.IGNORECASE):
        prefs.append("Unknown")

    return dedupe_preserve_order(prefs)


def should_reject_by_name_and_type(name: str, types: List[str]) -> bool:
    norm_name = normalized_text(name)
    specific_types = [t for t in types if t not in GENERIC_TYPES]

    # If only generic type and name is weak -> reject
    if not specific_types and not looks_like_real_entity_name(name):
        return True

    # Strongly suspicious combos
    suspicious = [
        (r"\bparque\b", {"Basilica", "Cathedral", "Castle", "TownHall", "Monument"}),
        (r"\bfestival\b", {"Castle", "Cathedral", "Basilica", "TownHall"}),
        (r"\barena\b", {"Castle", "Cathedral", "Basilica", "TownHall"}),
        (r"\bhotel\b", {"Cathedral", "Castle", "Basilica", "TownHall", "Monument"}),
        (r"\balbergue\b", {"Cathedral", "Castle", "Basilica", "TownHall", "Monument"}),
        (r"\bmuseo\b", {"Cathedral", "Castle", "Basilica", "TownHall"}),
        (r"\bmercado\b", {"Cathedral", "Castle", "Basilica", "TownHall"}),
        (r"\bcaf[eé]\b", {"Cathedral", "Castle", "Basilica", "TownHall", "Monument"}),
    ]

    for pattern, banned_types in suspicious:
        if re.search(pattern, norm_name, flags=re.IGNORECASE):
            if any(t in banned_types for t in specific_types):
                return True

    return False


# ---------------------------------------------------------------------
# Page-level logic
# ---------------------------------------------------------------------

def is_listing_like_page(page_url: str) -> bool:
    url = safe_str(page_url).lower()
    if not url:
        return False

    for pattern in LISTING_URL_PATTERNS + SECTION_URL_PATTERNS:
        if re.search(pattern, url, flags=re.IGNORECASE):
            return True
    return False


def is_probable_false_positive(name: str, page_url: str, types: List[str]) -> bool:
    norm_name = normalized_text(name)
    specific_types = [t for t in types if t not in GENERIC_TYPES]

    # On listing pages, generic/weak names should not survive
    if page_url and is_listing_like_page(page_url):
        weak_name_signals = [
            r"\bsi\b",
            r"\bdesde\b",
            r"\bconsignas\b",
            r"\bfamilias\b",
            r"\bgastronomia\b",
            r"\bturismo\b",
            r"\bexcursiones\b",
            r"\bmapas\b",
            r"\blugares\b",
        ]
        if any(re.search(pat, norm_name, flags=re.IGNORECASE) for pat in weak_name_signals):
            return True

        if not specific_types and has_listing_pollution(name):
            return True

    # Specific known junk-like forms
    blacklist_patterns = [
        r"^familias\s+si$",
        r"^consignas\s+mapas$",
        r"^castillo\s+lugares$",
        r"^hotel\s+leyre\s+ver$",
        r"^mercado\s+de\s+ermitagaña\s+ver$",
        r"^santiago\s+gastronomia\s+turismo$",
    ]
    if any(re.search(pat, norm_name, flags=re.IGNORECASE) for pat in blacklist_patterns):
        return True

    return False


# ---------------------------------------------------------------------
# Optional batch helper
# ---------------------------------------------------------------------

def validate_candidates(candidates: List[Dict[str, Any]], page_url: str = "") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for cand in candidates or []:
        validated = validate_candidate(cand, page_url=page_url)
        if validated is not None:
            out.append(validated)
    return out