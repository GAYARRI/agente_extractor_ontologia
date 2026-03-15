import spacy
import re

class TourismEntityExtractor:

    def __init__(self):

        self.nlp = spacy.load("es_core_news_md")

        self.bad_words = {
            "aquí","ideal","perfecta","perfectas","desde","practica",
            "navega","zarpa","utilizamos","disfruta","más","todo",
            "nuestro","nuestra","este","esta","estos","estas"
        }

        self.bad_patterns = [
            r"utilizamos cookies",
            r"más info",
            r"leer más",
            r"todo lo que necesitas"
        ]


    def clean_text(self, text):

        text = re.sub(r"\s+", " ", text)

        for p in self.bad_patterns:
            text = re.sub(p, "", text, flags=re.IGNORECASE)

        return text.strip()


    def extract(self, text):

        text = self.clean_text(text)

        doc = self.nlp(text)

        entities = []

        for ent in doc.ents:

            entity = ent.text.strip()

            if entity.lower() in self.bad_words:
                continue

            if len(entity) < 3:
                continue

            if len(entity.split()) < 2:
                continue

            entities.append(entity)

        return list(set(entities))