import re


class EntityTrimmer:

    def trim(self, entity):

        words = entity.split()

        # si es larga → quedarse con parte final (más informativa)
        if len(words) > 6:
            return " ".join(words[-4:])

        return entity