import re

class EntitySplitter:

    def split(self, entity):

        if not entity:
            return []

        # 🔥 detectar múltiples entidades típicas
        parts = re.split(
            r"(Semana Santa|Romería de Piedraescrita|Fiesta de la Chanfaina)",
            entity
        )

        results = []

        for p in parts:
            p = p.strip()

            if len(p) > 3:
                results.append(p)

        return list(set(results))