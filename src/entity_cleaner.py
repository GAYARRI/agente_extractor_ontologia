import re


STOP_WORDS = [
    "portada",
    "inicio",
    "home",
    "menu",
    "buscar",
    "contacto",
    "mapa",
    "cookies",
    "facebook",
    "instagram",
    "youtube",
    "rss",
    "twitter",
    "agenda",
    "eventos",
    "turismo",
]


class EntityCleaner:

    def clean(self, entities):

        clean_entities = []

        for e in entities:

            text = e.get("entity")

            if not text:
                continue

            text = text.strip()

            if len(text) < 4:
                continue

            text_lower = text.lower()

            # eliminar palabras de navegación
            if any(w in text_lower for w in STOP_WORDS):
                continue

            # eliminar entidades con números
            if re.search(r"\d", text):
                continue

            clean_entities.append(e)

        return clean_entities