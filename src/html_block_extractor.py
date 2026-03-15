from bs4 import BeautifulSoup


MIN_TEXT_LENGTH = 20


class HTMLBlockExtractor:

    def extract(self, html):

        soup = BeautifulSoup(html, "html.parser")

        blocks = []

        # eliminar elementos de ruido
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # extraer TODO el texto visible
        text = soup.get_text("\n")

        lines = text.split("\n")

        for line in lines:

            line = line.strip()

            if not line:
                continue

            if len(line) < MIN_TEXT_LENGTH:
                continue

            blocks.append({
                "text": line,
                "image": None
            })

        return blocks