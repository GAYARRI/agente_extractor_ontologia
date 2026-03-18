class DescriptionExtractor:

    def extract(self, entity, text):

        text = text.strip()

        # 🔹 SHORT DESCRIPTION (1 frase)
        short = self._get_first_sentence(text)

        # 🔹 LONG DESCRIPTION (fragmento limpio)
        long = self._get_long_description(text)

        return {
            "short_description": short,
            "long_description": long
        }

    def _get_first_sentence(self, text):

        parts = text.split(".")

        if parts:
            return parts[0].strip()

        return text[:120]

    def _get_long_description(self, text):

        # máximo 300 chars limpio
        return text[:300].strip()