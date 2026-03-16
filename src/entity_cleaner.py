import re


class EntityCleaner:

    def __init__(self):

        # palabras que suelen aparecer en menús web
        self.stopwords = {
            "inicio",
            "agenda",
            "eventos",
            "contenido",
            "principal",
            "planifica",
            "visita",
            "dónde",
            "donde",
            "qué",
            "que",
            "hacer",
            "comer",
            "dormir",
            "mapa",
            "interactivo",
            "noticias",
            "utilidades",
            "encuestas"
        }


    def clean(self, entities):

        cleaned = []

        for entity in entities:

            if not entity:
                continue

            text = entity.strip()

            # eliminar puntuación final
            text = re.sub(r"[^\w\sáéíóúÁÉÍÓÚñÑ]", "", text)

            # evitar entidades demasiado cortas
            if len(text) < 4:
                continue

            words = text.lower().split()

            # eliminar menús web
            if any(w in self.stopwords for w in words):
                continue

            # evitar combinaciones incorrectas de eventos
            # ej: "Chanfaina Romería"
            if text.lower().startswith(("romería", "fiesta", "semana")) and " de " not in text.lower():
                continue

            # evitar entidades solo numéricas
            if text.isdigit():
                continue

            # capitalización simple
            text = text.title()

            if entity.endswith("Ideal"):
                continue

            if entity.startswith("Copyright"):
                continue

            cleaned.append(text)

        return cleaned