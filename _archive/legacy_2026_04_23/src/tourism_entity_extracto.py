# tourism_entity_extractor.py

import re

ENTITY_PATTERN = re.compile(
    r"""
    (Catedral|Iglesia|Basílica|Museo|Palacio|Parque|Plaza|Castillo|Puente|Teatro|Centro|Monasterio|Ciudadela|Muralla|Ruta|Camino)
    \s+(?:de|del|la|el|los|las)?\s*
    ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,4})
    """,
    re.VERBOSE
)

BAD_PATTERNS = [
    r"\b(no sabes|descubre|encuentra|reserva|actividad|contenido)\b",
]

def is_valid_entity(text: str) -> bool:
    if len(text.split()) > 6:
        return False
    if any(re.search(p, text.lower()) for p in BAD_PATTERNS):
        return False
    tokens = text.split()
    caps = sum(1 for t in tokens if t[:1].isupper())
    return caps >= 2

def extract_entities(text: str):
    candidates = []
    for match in ENTITY_PATTERN.finditer(text):
        name = match.group(0).strip()
        if is_valid_entity(name):
            candidates.append(name)
    return list(set(candidates))
