from bs4 import BeautifulSoup


NAVIGATION_WORDS = {
    "utilidades",
    "encuestas",
    "recomendador",
    "incidencias",
    "noticias",
    "mapa",
    "inicio"
}


NOISE_PATTERNS = [
    "copyright",
    "todos los derechos reservados",
    "política de privacidad",
    "cookies",
    "aviso legal"
]


class HTMLBlockExtractor:

    def is_noise(self, text):

        t = text.lower()

        for p in NOISE_PATTERNS:
            if p in t:
                return True

        return False


    def is_navigation(self, text):

        t = text.lower()

        for word in NAVIGATION_WORDS:
            if word in t:
                return True

        return False


    def extract(self, html):

        soup = BeautifulSoup(html, "html.parser")

        blocks = []

        seen = set()

        # ❗ quitamos <a> para evitar ruido
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):

            text = tag.get_text(" ", strip=True)

            if not text:
                continue

            # tamaño mínimo
            if len(text) < 25:
                continue

            # evitar bloques gigantes
            if len(text) > 300:
                continue

            # navegación
            if self.is_navigation(text):
                continue

            # ruido
            if self.is_noise(text):
                continue

            # evitar duplicados
            if text in seen:
                continue

            seen.add(text)

            blocks.append({
                "text": text
            })

        return blocks