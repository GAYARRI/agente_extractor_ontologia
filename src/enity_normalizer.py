import re


class EntityNormalizer:

    def normalize(self, entity):

        entity = entity.strip()

        # eliminar paréntesis
        entity = re.sub(r"\(.*?\)", "", entity)

        # eliminar dobles espacios
        entity = re.sub(r"\s+", " ", entity)

        # normalización básica
        entity = entity.replace("Provincia de ", "")

        return entity.strip()