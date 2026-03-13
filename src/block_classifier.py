from bs4 import BeautifulSoup
import re


class BlockClassifier:

    def __init__(self):

        # palabras típicas del dominio turismo
        self.tourism_keywords = [
            "playa",
            "sendero",
            "ruta",
            "hotel",
            "puerto",
            "valle",
            "parque",
            "monumento",
            "iglesia",
            "catedral",
            "museo",
            "jardín",
            "jardin",
            "festival",
            "carnaval",
            "naturaleza",
            "montaña",
            "mirador",
            "dunas",
            "isla",
        ]

        # ruido típico de interfaz web
        self.ui_noise = [
            "share",
            "copy link",
            "watch later",
            "tap to unmute",
            "youtube",
            "search",
            "cookie",
            "cookies",
            "login",
            "newsletter",
            "subscribe",
        ]

    # --------------------------------------------------
    # LIMPIAR TEXTO
    # --------------------------------------------------

    def clean_text(self, text):

        text = re.sub(r"\s+", " ", text)

        return text.strip()

    # --------------------------------------------------
    # DETECTAR HEADING
    # --------------------------------------------------

    def extract_heading(self, soup):

        for tag in ["h1", "h2", "h3", "h4"]:
            h = soup.find(tag)
            if h:
                return h.get_text(strip=True)

        return None

    # --------------------------------------------------
    # DETECTAR CANDIDATO DESDE TEXTO
    # --------------------------------------------------

    def guess_entity_from_text(self, text):

        if not text:
            return None

        text = text.strip()

        if len(text) < 10:
            return None

        # usar primera frase
        sentence = text.split(".")[0]

        if len(sentence) < 5:
            return None

        return sentence[:80]

    # --------------------------------------------------
    # CLASIFICAR BLOQUE
    # --------------------------------------------------

    def classify_block(self, html_block):

        if not html_block or not isinstance(html_block, str):
            return None

        soup = BeautifulSoup(html_block, "html.parser")

        text = soup.get_text(" ", strip=True)

        if not text:
            return None

        text = self.clean_text(text)

        text_lower = text.lower()

        # -----------------------------------------
        # FILTRO DE UI
        # -----------------------------------------

        for noise in self.ui_noise:
            if noise in text_lower:
                return None

        # -----------------------------------------
        # DETECTAR HEADING
        # -----------------------------------------

        heading = self.extract_heading(soup)

        # -----------------------------------------
        # SI NO HAY HEADING, USAR TEXTO
        # -----------------------------------------

        if not heading:

            heading = self.guess_entity_from_text(text)

            if not heading:
                return None

        # -----------------------------------------
        # VALIDAR LONGITUD
        # -----------------------------------------

        if len(heading) < 3:
            return None

        # -----------------------------------------
        # SCORE POR KEYWORDS TURÍSTICAS
        # -----------------------------------------

        keyword_score = 0

        for kw in self.tourism_keywords:

            if kw in text_lower:
                keyword_score += 1

        # -----------------------------------------
        # FILTRO DE BLOQUES DEMASIADO PEQUEÑOS
        # -----------------------------------------

        if keyword_score == 0 and len(text) < 80:
            return None

        # -----------------------------------------
        # RESULTADO
        # -----------------------------------------

        return {
            "entity_candidate": heading.strip(),
            "score": keyword_score,
            "text": text[:800],
        }