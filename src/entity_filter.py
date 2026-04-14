import re
import unicodedata


UI_EXACT = {
    "leer más",
    "leer mas",
    "más info",
    "mas info",
    "en familia",
    "te queda mucho por descubrir",
    "te queda mucho por descubrir:",
    "descubre",
    "inicio",
    "home",
}

GENERIC_SINGLE_TOKEN_BLOCKLIST = {
    "bienal",
    "academias",
    "niña",
    "tablaos",
    "flamenco",
    "sevillanos",
    "visitantes",
}

GENERIC_MULTIWORD_BLOCKLIST = {
    "tablaos flamencos",
    "academias de flamenco",
    "sevilla academias",
}

PERSON_LIKE_TITLES = {
    "la niña de los peines",
    "niña de los peines",
    "manolo caracol",
}

CONCEPT_LIKE_PHRASES = {
    "cante jondo",
    "tablaos flamencos",
    "academias de flamenco",
}


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def normalize_entity_text(text: str) -> str:
    text = text or ""
    text = text.strip()
    text = re.sub(r"^\d+[_\-\.\)]\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .,;:!¡?¿\"'“”‘’()[]{}")
    return text.strip()


def canonical_entity_key(text: str) -> str:
    text = normalize_entity_text(text).lower()
    text = _strip_accents(text)
    return text


def looks_like_ui_fragment(text: str) -> bool:
    t = canonical_entity_key(text)
    if not t:
        return True

    if t in UI_EXACT:
        return True

    if re.fullmatch(r"\d+_?", t):
        return True

    if any(x in t for x in ["leer más", "leer mas", "más info", "mas info"]):
        return True

    if t.startswith("01 ") or t.startswith("02 ") or t.startswith("03 "):
        return True

    return False


def is_generic_entity(text: str) -> bool:
    t = canonical_entity_key(text)
    if not t:
        return True

    if t in GENERIC_SINGLE_TOKEN_BLOCKLIST:
        return True

    if t in GENERIC_MULTIWORD_BLOCKLIST:
        return True

    if t in CONCEPT_LIKE_PHRASES:
        return True

    words = t.split()

    # plural común sin mayúsculas semánticas
    if len(words) >= 2 and all(w.isalpha() for w in words):
        if words[-1].endswith("s") and t == t.lower():
            if t not in PERSON_LIKE_TITLES:
                return True

    return False


def is_person_like_entity(text: str) -> bool:
    t = canonical_entity_key(text)

    if t in PERSON_LIKE_TITLES:
        return True

    words = normalize_entity_text(text).split()
    if len(words) >= 2 and all(w[:1].isupper() for w in words if w[:1].isalpha()):
        return True

    return False


def is_valid_entity(entity: str, context: str = "") -> bool:
    
    entity = normalize_entity_text(entity)
    name = e["entity"].lower()
    if not entity:
        return False

    e = canonical_entity_key(entity)
    words = entity.split()
    context_l = (context or "").lower()

    if len(words) > 8 or len(entity) < 3:
        return False

    if looks_like_ui_fragment(entity):
        return False

    if any(x in e for x in ["wenn", "sie", "und", "les", "des", "comment", "arriver"]):
        return False

    # bloquea one-token ambiguos salvo excepciones reales
    if len(words) == 1:
        if e in {"sevilla", "triana"}:
            return True
        return False

    # bloquea conceptos/categorías genéricas salvo que el contexto los convierta
    # en una instancia concreta muy clara
    if is_generic_entity(entity):
        if "bienal de flamenco" in context_l and e == "bienal":
            return False
        return False

    return True