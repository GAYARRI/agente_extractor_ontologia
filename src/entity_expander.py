import re


class EntityExpander:

    def expand(self, entity, text):

        entity = entity.strip()

        # buscar frases con mayúsculas razonables
        pattern = re.compile(r'([A-ZÁÉÍÓÚÑ][\wáéíóúñ\s]{3,60})')

        matches = pattern.findall(text)

        best_match = entity

        for m in matches:

            # debe contener la entidad
            if entity.lower() in m.lower():

                # evitar frases largas basura
                if len(m.split()) > 6:
                    continue

                # evitar frases con verbos
                if any(v in m.lower() for v in [
                    "vive", "explora", "descubre",
                    "navega", "disfruta"
                ]):
                    continue

                if len(m) > len(best_match):
                    best_match = m.strip()

        return best_match