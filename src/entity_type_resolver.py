import re
import unicodedata


def _norm(text: str) -> str:
    text = text or ""
    text = text.strip().lower()
    text = "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )
    return re.sub(r"\s+", " ", text)


class EntityTypeResolver:
    def __init__(self):
        self.person_keywords = [
            "cantaor", "cantaora", "artista", "bailaor", "bailaora",
            "figura", "voz", "interprete", "interprete", "historia",
            "fue", "nacio", "murio",
        ]

        self.event_keywords = [
            "festival", "evento", "bienal", "edicion", "celebra",
        ]

        self.place_keywords = [
            "altozano", "barrio", "plaza", "calle", "alcazar",
            "parque", "museo", "teatro", "tablao", "isla magica",
        ]

        self.organization_keywords = [
            "fundacion", "asociacion", "academia", "centro",
        ]

        self.concept_keywords = [
            "arte", "cante", "baile", "poesia", "sentimiento",
            "cante jondo", "tablaos flamencos", "academias de flamenco",
        ]

        self.person_exact = {
            "manolo caracol",
            "la nina de los peines",
            "nina de los peines",
            "pastora pavon",
        }

        self.event_exact = {
            "bienal de flamenco",
            "bienal de flamenco de sevilla",
        }

        self.place_exact = {
            "sevilla",
            "triana",
            "altozano de triana",
            "real alcazar",
            "isla magica",
        }

        self.concept_exact = {
            "flamenco",
            "cante jondo",
            "tablaos flamencos",
            "academias de flamenco",
            "sevilla academias",
        }

    def resolve(self, mention, context="", block_text=""):
        mention_n = _norm(mention)
        context_n = _norm(f"{context} {block_text}")

        if mention_n in self.person_exact:
            return {"class": "Person", "confidence": 0.95}

        if mention_n in self.event_exact:
            return {"class": "Event", "confidence": 0.95}

        if mention_n in self.place_exact:
            return {"class": "Place", "confidence": 0.95}

        if mention_n in self.concept_exact:
            return {"class": "Concept", "confidence": 0.92}

        if any(k in context_n for k in self.person_keywords):
            if len(mention.split()) >= 2:
                return {"class": "Person", "confidence": 0.88}

        if any(k in mention_n for k in self.event_keywords) or any(k in context_n for k in self.event_keywords):
            if "bienal" in mention_n and "bienal de flamenco" not in context_n:
                return {"class": "Concept", "confidence": 0.55}
            return {"class": "Event", "confidence": 0.84}

        if any(k in mention_n for k in self.organization_keywords):
            return {"class": "Organization", "confidence": 0.80}

        if any(k in mention_n for k in self.place_keywords):
            return {"class": "Place", "confidence": 0.82}

        if any(k in mention_n for k in self.concept_keywords):
            return {"class": "Concept", "confidence": 0.80}

        # fallback más conservador
        return {"class": "Thing", "confidence": 0.40}