from bs4 import BeautifulSoup


class HTMLBlockExtractor:
    def __init__(self, min_text_length=60):
        self.min_text_length = min_text_length

    def _clean_text(self, text: str) -> str:
        return " ".join(text.strip().split())

    def extract_blocks(self, html, page_url=""):
        soup = BeautifulSoup(html, "html.parser")
        blocks = []

        candidates = soup.find_all(["section", "article", "div", "li"])

        for idx, node in enumerate(candidates):
            text = self._clean_text(node.get_text(" ", strip=True))
            if len(text) < self.min_text_length:
                continue

            heading_tag = node.find(["h1", "h2", "h3", "h4"])
            heading = self._clean_text(heading_tag.get_text(" ", strip=True)) if heading_tag else ""

            img = node.find("img")
            image = img.get("src") if img and img.get("src") else None

            links = []
            for a in node.find_all("a", href=True):
                href = a.get("href", "").strip()
                if href:
                    links.append(href)

            blocks.append({
                "block_id": f"block_{idx}",
                "heading": heading,
                "text": text,
                "image": image,
                "links": links,
                "page_url": page_url,
            })

        return blocks