import re


class TourismEntityExtractor:

    def __init__(self):

        self.bad_words = {
            "aquí","ideal","perfecta","perfectas","desde",
            "practica","navega","zarpa","utilizamos",
            "disfruta","más","todo","este","esta"
        }

        # patrones típicos de entidades turísticas
        self.entity_patterns = [
            r"Playa de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
            r"San [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
            r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
            r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+"
        ]


    def clean_text(self, text):

        text = re.sub(r"\s+", " ", text)

        text = re.sub(r"utilizamos cookies.*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"más info", "", text, flags=re.IGNORECASE)

        return text.strip()


    def extract(self, text):

        text = self.clean_text(text)

        entities = []

        for pattern in self.entity_patterns:

            matches = re.findall(pattern, text)

            for m in matches:

                entity = m.strip()

                if entity.lower() in self.bad_words:
                    continue

                if len(entity.split()) < 2:
                    continue

                entities.append(entity)

        return list(set(entities))