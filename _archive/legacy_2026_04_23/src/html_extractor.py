from bs4 import BeautifulSoup
import trafilatura


def html_extractor(html):

    # Intento 1 → trafilatura
    text = trafilatura.extract(html)

    if text and len(text) > 1000:
        return text

    # fallback → BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)

    return text