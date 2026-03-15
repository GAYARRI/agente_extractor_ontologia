import unicodedata


class EntityCanonicalizer:

    def canonical_key(self, text):

        text = text.lower()

        text = unicodedata.normalize("NFKD", text)

        text = "".join(c for c in text if not unicodedata.combining(c))

        text = text.replace(" ", "_")

        return text