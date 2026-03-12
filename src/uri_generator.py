import re


class URIGenerator:

    def __init__(self, base_uri="https://tourismkg.com/resource/"):

        self.base_uri = base_uri

    # ------------------------------

    def normalize(self, text):

        text = text.lower()

        text = text.replace("á", "a")
        text = text.replace("é", "e")
        text = text.replace("í", "i")
        text = text.replace("ó", "o")
        text = text.replace("ú", "u")
        text = text.replace("ñ", "n")

        text = re.sub(r"[^a-z0-9\s]", "", text)

        text = re.sub(r"\s+", "_", text)

        return text

    # ------------------------------

    def generate(self, entity):

        normalized = self.normalize(entity)

        return self.base_uri + normalized