from bs4 import BeautifulSoup


class HTMLBlockExtractor:

    def __init__(self):
        pass

    # ==================================================
    # FILTRO DE TAGS BASURA
    # ==================================================

    def remove_noise(self, soup):

        # ❌ eliminar completamente
        for tag in soup([
            "script", "style", "nav", "header", "footer",
            "aside", "form", "noscript"
        ]):
            tag.decompose()

        return soup

    # ==================================================
    # FILTRO DE CLASES HTML
    # ==================================================

    def is_noise_block(self, element):

        if not element:
            return True

        classes = " ".join(element.get("class", [])).lower()

        noise_keywords = [
            "menu", "nav", "header", "footer",
            "sidebar", "cookie", "banner",
            "login", "form", "search"
        ]

        if any(k in classes for k in noise_keywords):
            return True

        return False

    # ==================================================
    # BLOQUES DE CONTENIDO
    # ==================================================

    def extract(self, html):

        soup = BeautifulSoup(html, "html.parser")

        soup = self.remove_noise(soup)

        blocks = []

        # 🔥 SOLO CONTENIDO REAL
        candidates = soup.find_all(["section", "article", "div", "p"])

        for el in candidates:

            if self.is_noise_block(el):
                continue

            text = el.get_text(" ", strip=True)

            # 🔥 FILTROS CLAVE
            if not text:
                continue

            if len(text) < 60:
                continue

            # ❌ evitar navegación / UI
            if any(x in text.lower() for x in [
                "phone number",
                "email",
                "login",
                "register",
                "password",
                "cookies"
            ]):
                continue

            blocks.append({
                "text": text
            })

        return blocks