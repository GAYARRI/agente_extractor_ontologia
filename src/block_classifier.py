from bs4 import BeautifulSoup
import re


class BlockClassifier:

    def __init__(self):

        self.stop_entities = {

            "ver más",
            "copyright",
            "aviso legal",
            "política de privacidad",
            "contacto",
            "agenda",
            "organiza tu viaje",
            "qué hacer",
            "qué puedes hacer"
        }

        self.tourism_keywords = [

            "playa",
            "ruta",
            "sendero",
            "hotel",
            "evento",
            "festival",
            "carnaval",
            "parque",
            "naturaleza",
            "mirador",
            "isla",
            "pueblo",
            "ciudad",
            "mar",
            "atlántico",
            "buceo",
            "surf",
            "senderismo",
            "gastronomía"
        ]


    def clean_entity(self, text):

        text = re.sub(r"\s+", " ", text)

        text = text.strip()

        return text


    def is_valid_entity(self, text):

        if not text:
            return False

        text = text.lower().strip()

        if len(text) < 3:
            return False

        if text in self.stop_entities:
            return False

        return True


    def keyword_score(self, text):

        score = 0

        text = text.lower()

        for k in self.tourism_keywords:

            if k in text:
                score += 1

        return score


    def classify_block(self, block_html):

        soup = BeautifulSoup(block_html, "html.parser")

        text = soup.get_text(" ", strip=True)

        if not text:
            return None

        heading = soup.find(["h1", "h2", "h3"])

        entity_candidate = None

        if heading:

            entity_candidate = heading.get_text(strip=True)

        else:

            words = text.split(" ")

            entity_candidate = " ".join(words[:6])

        entity_candidate = self.clean_entity(entity_candidate)

        if not self.is_valid_entity(entity_candidate):
            return None

        keyword_score = self.keyword_score(text)

        if keyword_score == 0 and len(text) < 80:
            return None

        return {

            "entity_candidate": entity_candidate,

            "score": keyword_score,

            "text": text

        }