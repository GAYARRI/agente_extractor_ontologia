import re

STOPWORDS_START = {
    "Desde", "Vive", "Explora", "Navega",
    "Practica", "Descubre", "Una", "Un",
    "La", "El"
}

BAD_TOKENS = {
    "Practica", "Vive", "Explora"
}


class EntityCleaner:

    def clean(self, entities):

        cleaned = []

        for e in entities:

            if not e:
                continue

            text = e.strip()

            # -----------------------------
            # eliminar stopwords iniciales
            # -----------------------------
            words = text.split()

            while words and words[0] in STOPWORDS_START:
                words.pop(0)

            text = " ".join(words)

            # -----------------------------
            # eliminar tokens basura
            # -----------------------------
            text = " ".join(
                w for w in text.split()
                if w not in BAD_TOKENS
            )

            # -----------------------------
            # limpiar símbolos
            # -----------------------------
            text = re.sub(r"[^\w\sáéíóúÁÉÍÓÚñÑ]", "", text)

            # -----------------------------
            # evitar cosas muy cortas
            # -----------------------------
            if len(text) < 3:
                continue

            cleaned.append(text.strip())

        return cleaned