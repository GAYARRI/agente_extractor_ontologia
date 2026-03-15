from bs4 import BeautifulSoup


class HTMLBlockExtractor:

    def __init__(self):

        self.block_tags = [
            "section",
            "article",
            "div",
            "li"
        ]


    def extract(self, html):

        soup = BeautifulSoup(html, "html.parser")

        blocks = []

        for tag in self.block_tags:

            elements = soup.find_all(tag)

            for el in elements:

                text = el.get_text(" ", strip=True)

                if not text:
                    continue

                img = None

                img_tag = el.find("img")

                if img_tag and img_tag.get("src"):
                    img = img_tag["src"]

                block = {
                    "text": text,
                    "image": img
                }

                blocks.append(block)

        return blocks