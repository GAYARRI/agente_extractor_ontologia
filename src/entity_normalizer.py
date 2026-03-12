import re
import unicodedata


class EntityNormalizer:

    def __init__(self):

        self.stopwords = [
            "el", "la", "los", "las",
            "de", "del",
            "the"
        ]


    def normalize(self, name):

        if not name:
            return None

        # eliminar espacios
        name = name.strip()

        # quitar acentos
        name = unicodedata.normalize("NFD", name)
        name = "".join(c for c in name if unicodedata.category(c) != "Mn")

        # minúsculas
        name = name.lower()

        # eliminar artículos iniciales
        words = name.split()

        if words and words[0] in self.stopwords:
            words = words[1:]

        name = " ".join(words)

        # eliminar texto entre paréntesis
        name = re.sub(r"\(.*?\)", "", name)

        # limpiar espacios
        name = " ".join(name.split())

        return name


    def uri(self, name):

        name = self.normalize(name)

        if not name:
            return None

        # convertir a URI
        uri = name.replace(" ", "_")

        # eliminar caracteres raros
        uri = re.sub(r"[^a-z0-9_]", "", uri)

        return uri