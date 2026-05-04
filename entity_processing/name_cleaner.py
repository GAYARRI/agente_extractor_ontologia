import re
from typing import Any, Dict

from .config import (
    BAD_NAME_TOKENS,
    CLASS_NAME_ANCHORS,
    CONTEXTUAL_NAME_TOKENS,
    EVENT_SPECIAL_PHRASES,
    LEADING_CLASS_OVERRIDES,
    MONUMENT_BROAD_PLACE_EXACT,
    MONUMENT_BROAD_PLACE_TOKENS,
    MONUMENT_CONTEXTUAL_ALLOWED_TERMS,
    MONUMENT_HARD_REJECT_EXACT,
    MONUMENT_HARD_REJECT_PREFIXES,
    MONUMENT_NATURAL_RESOURCE_EXACT,
    MONUMENT_PERSONLIKE_EXCEPTIONS,
    MONUMENT_STRONG_NOISE_TOKENS,
    NAME_STOP_SUFFIXES,
    TOWNHALL_ALLOWED_NAME_TOKENS,
)
from .normalize import normalized_token_text
from .text_cleaning import clean_text


def extract_raw_name(entity: Dict[str, Any]) -> str:
    return (
        str(
            entity.get("name")
            or entity.get("entity_name")
            or entity.get("entity")
            or entity.get("label")
            or ""
        ).strip()
    )


def clean_entity_name(raw_name: str) -> str:
    name = clean_text(raw_name).strip()

    # cut obvious sentence continuation
    name = re.split(r"[.:;]\s+", name)[0].strip()

    # remove repeated spaces
    name = re.sub(r"\s+", " ", name).strip()

    # remove long mixed tails after strong separators
    for sep in [" – ", " - ", " | "]:
        if sep in name:
            name = name.split(sep)[0].strip()

    tokens = name.split()
    cleaned_tokens = []

    for token in tokens:
        low = normalized_token_text(token)
        if low in NAME_STOP_SUFFIXES and len(cleaned_tokens) >= 2:
            break
        cleaned_tokens.append(token)

    name = " ".join(cleaned_tokens).strip()
    if len(cleaned_tokens) >= 2:
        last_token = normalized_token_text(cleaned_tokens[-1])
        if last_token in NAME_STOP_SUFFIXES:
            name = " ".join(cleaned_tokens[:-1]).strip()

    # remove awkward tail words again
    name = re.sub(r"\s+", " ", name).strip()

    return name


def _strip_contextual_tail(cleaned_name: str, primary_class: str = "") -> str:
    normalized = normalized_token_text(cleaned_name)
    if not normalized:
        return cleaned_name

    anchor_hints = CLASS_NAME_ANCHORS.get(str(primary_class or "").strip(), set())
    if anchor_hints and not any(hint in normalized for hint in anchor_hints):
        return cleaned_name

    tokens = cleaned_name.split()
    if len(tokens) < 2:
        return cleaned_name

    last_good = len(tokens)
    for i, token in enumerate(tokens):
        low = normalized_token_text(token)
        if low in CONTEXTUAL_NAME_TOKENS and i >= 2:
            last_good = i
            break

    trimmed = " ".join(tokens[:last_good]).strip(" -|,;:")
    return trimmed or cleaned_name


def canonicalize_entity_name(name: str, primary_class: str = "") -> str:
    cleaned_base = clean_entity_name(name)
    primary = str(primary_class or "").strip()
    normalized_base = normalized_token_text(cleaned_base)
    anchor_hints = CLASS_NAME_ANCHORS.get(primary, set())

    if primary == "Route":
        return cleaned_base

    # Preserve canonical names like "Museo de la Evolución" or
    # "Iglesia de San ..." that were being truncated by contextual-tail cleanup.
    if anchor_hints and " de " in normalized_base:
        for hint in anchor_hints:
            hint = str(hint or "").strip()
            if not hint:
                continue
            if (
                normalized_base == hint
                or normalized_base.startswith(hint + " ")
                or f"{hint} de " in normalized_base
            ):
                return cleaned_base

    cleaned = _strip_contextual_tail(cleaned_base, primary_class)

    if primary == "TownHall":
        return cleaned

    return cleaned


def infer_name_implied_class(name: str) -> str:
    normalized = normalized_token_text(clean_entity_name(name))
    if not normalized:
        return ""

    for prefix, target_class in LEADING_CLASS_OVERRIDES.items():
        if normalized.startswith(prefix.strip() + " ") or normalized == prefix.strip():
            return target_class

    return ""


def infer_monument_replacement_class(name: str, url: str = "") -> str:
    normalized = normalized_token_text(clean_entity_name(name))
    url_norm = normalized_token_text(url)
    if not normalized:
        return ""

    if any(token in normalized for token in ("festival", "concierto", "conciertos", "exposicion", "exposiciones", "evento", "eventos", "rock")):
        return "Event"
    if "/evento/" in url_norm and any(token in normalized for token in ("miradas", "eventos", "conciertos", "festival", "rock")):
        return "Event"

    if any(token in normalized for token in ("ruta", "rutas", "paseo", "paseos", "camino", "senderismo", "teatralizadas")):
        return "Route"

    if normalized.startswith("calle "):
        return "Street"

    if "fronton" in normalized or "frontón" in normalized:
        return "Stadium"

    if normalized in MONUMENT_NATURAL_RESOURCE_EXACT:
        return "NaturalResource"

    if normalized in MONUMENT_BROAD_PLACE_EXACT:
        return "HistoricalOrCulturalResource"

    if any(token in normalized for token in MONUMENT_BROAD_PLACE_TOKENS):
        return "HistoricalOrCulturalResource"

    if "catedral" in normalized or "claustros" in normalized or "campana" in normalized:
        return "Cathedral"

    if normalized.startswith("portal ") or normalized.endswith(" el portal"):
        return "Gate"

    return ""


def is_plausible_class_name(name: str, primary_class: str = "") -> bool:
    normalized = normalized_token_text(name)
    if not normalized:
        return False

    event_san_fermin = primary_class == "Event" and (
        "san fermin" in normalized or "san fermín" in normalized
    )
    event_special_phrase = primary_class == "Event" and normalized in EVENT_SPECIAL_PHRASES

    if primary_class == "Monument":
        tokens = [token for token in normalized.split() if token]
        if not tokens:
            return False
        if normalized in MONUMENT_HARD_REJECT_EXACT:
            return False
        if any(normalized.startswith(prefix + " ") or normalized == prefix for prefix in MONUMENT_HARD_REJECT_PREFIXES):
            return False

        if any(anchor in normalized for anchor in ("monumento", "estatua", "escultura", "memorial", "busto")):
            if "monumentos" in normalized and normalized not in MONUMENT_PERSONLIKE_EXCEPTIONS:
                return False
            return True

        if tokens[0] in MONUMENT_STRONG_NOISE_TOKENS or tokens[-1] in MONUMENT_STRONG_NOISE_TOKENS:
            return False
        noise_hits = sum(1 for token in tokens if token in MONUMENT_STRONG_NOISE_TOKENS)
        if noise_hits >= 2:
            return False

        if normalized in MONUMENT_PERSONLIKE_EXCEPTIONS:
            return True

        title_like_hits = sum(
            1 for token in tokens
            if token in MONUMENT_CONTEXTUAL_ALLOWED_TERMS
        )
        if title_like_hits == 0 and len(tokens) <= 4:
            return False

        return True

    anchor_hints = CLASS_NAME_ANCHORS.get(str(primary_class or "").strip(), set())
    if anchor_hints and not any(hint in normalized for hint in anchor_hints):
        if event_special_phrase:
            pass
        else:
            return False

    tokens = [token for token in normalized.split() if token]
    if event_san_fermin and not event_special_phrase:
        return False

    if event_special_phrase:
        return True

    if event_san_fermin:
        if len(tokens) >= 3 and any(token in CONTEXTUAL_NAME_TOKENS for token in tokens if token not in {"san", "fermin", "fermín", "txikito", "gora"}):
            return False

    if tokens:
        first_is_contextual = tokens[0] in CONTEXTUAL_NAME_TOKENS
        first_is_event_anchor = primary_class == "Event" and any(hint.startswith(tokens[0]) for hint in anchor_hints)
        if (first_is_contextual and not first_is_event_anchor) or tokens[-1] in CONTEXTUAL_NAME_TOKENS:
            return False

    if primary_class == "TownHall":
        extra_tokens = [
            token for token in tokens
            if token not in TOWNHALL_ALLOWED_NAME_TOKENS
        ]
        if any(token in CONTEXTUAL_NAME_TOKENS for token in extra_tokens):
            return False
        if len(extra_tokens) >= 2:
            return False
    elif anchor_hints:
        contextual_hits = sum(1 for token in tokens if token in CONTEXTUAL_NAME_TOKENS)
        if contextual_hits >= 2:
            return False

    return True


def looks_like_bad_name(name: str) -> bool:
    normalized = normalized_token_text(name)

    if not normalized:
        return True

    if len(normalized.split()) > 12:
        return True

    if re.search(r"\b\d+\s*…\s*\d+\b", normalized):
        return True

    bad_hits = sum(1 for token in BAD_NAME_TOKENS if token in normalized)
    if bad_hits >= 2:
        return True

    contextual_hits = sum(1 for token in CONTEXTUAL_NAME_TOKENS if token in normalized)
    if contextual_hits >= 2:
        return True

    return False
