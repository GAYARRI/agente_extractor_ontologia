from bs4 import BeautifulSoup


class HTMLBlockExtractor:

    def __init__(self):
        pass


    def clean_dom(self, soup):

        # eliminar ruido de navegación
        for tag in soup(["nav", "footer", "header", "script", "style", "noscript"]):
            tag.decompose()

        return soup


    def extract_blocks(self, html, page_url=None):

        soup = BeautifulSoup(html, "html.parser")

        soup = self.clean_dom(soup)

        blocks = []

        candidates = soup.find_all([
            "section",
            "article",
            "div"
        ])

        idx = 0

        for node in candidates:

            text = node.get_text(separator=" ", strip=True)

            if not text:
                continue

            if len(text) < 40:
                continue

            heading = None

            h = node.find(["h1", "h2", "h3"])

            if h:
                heading = h.get_text(strip=True)

            image = None

            img = node.find("img")

            if img and img.get("src"):
                image = img.get("src")

            links = []

            for a in node.find_all("a", href=True):

                href = a["href"]

                if href.startswith("/"):
                    links.append(href)

            blocks.append({

                "block_id": f"block_{idx}",

                "heading": heading,

                "text": text,

                "html": str(node),

                "image": image,

                "links": links,

                "page_url": page_url

            })

            idx += 1

        return blocks