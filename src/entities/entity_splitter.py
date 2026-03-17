import re


class EntitySplitter:

    def split(self, entity):

        # dividir por conectores
        parts = re.split(r'hasta|y|,', entity, flags=re.IGNORECASE)

        cleaned = []

        for p in parts:
            p = p.strip()

            if len(p.split()) <= 6:
                cleaned.append(p)

        return cleaned if len(cleaned) > 1 else [entity]