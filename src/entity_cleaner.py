import re


class EntityCleaner:

    def __init__(self):

        self.noise_patterns = [
            r"disfruta.*",
            r"descubre.*",
            r"vive.*",
            r"más info.*",
            r"utilizamos cookies.*",
            r"haz clic.*",
        ]

    def clean(self, text):

        if not text:
            return None

        text = text.strip()

        # eliminar frases ruido
        for pattern in self.noise_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # eliminar puntuación final
        text = re.sub(r"[^\w\sáéíóúñÁÉÍÓÚÑ]", "", text)

        # colapsar espacios
        text = re.sub(r"\s+", " ", text)

        text = text.strip()

        if len(text) < 3:
            return None

        return text