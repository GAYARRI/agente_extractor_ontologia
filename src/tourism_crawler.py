import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


VALID_PATH_KEYWORDS = [
    "destino",
    "destinos",
    "experiencia",
    "experiencias",
    "agenda",
    "evento",
    "que-no-te-lo-cuenten",
    "naturaleza",
    "cultura",
    "patrimonio"
]

INVALID_PATH_KEYWORDS = [
    "login",
    "contacto",
    "mapa",
    "mapas",
    "folletos",
    "privacidad",
    "cookies"
]


class TourismCrawler:

    def __init__(self, start_url, max_pages=1000):

        self.start_url = start_url
        self.max_pages = max_pages


    def crawl(self):

        visited = set()
        to_visit = [self.start_url]

        pages = []

        headers = {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        session = requests.Session()
        session.headers.update(headers)

        while to_visit and len(pages) < self.max_pages:

            url = to_visit.pop(0)

            if url in visited:
                continue

            visited.add(url)

            try:

                response = session.get(url, timeout=15)

                html = response.text

                if "requested url was rejected" in html.lower():
                    print("⚠️ Página bloqueada:", url)
                    continue

                pages.append((url, html))

                soup = BeautifulSoup(html, "html.parser")

                links = soup.find_all("a")

                for link in links:

                    href = link.get("href")

                    if not href:
                        continue

                    href = urljoin(self.start_url, href)

                    if href in visited:
                        continue

                    href_lower = href.lower()

                    # evitar páginas irrelevantes
                    if any(x in href_lower for x in INVALID_PATH_KEYWORDS):
                        continue

                    # priorizar páginas turísticas
                    if any(x in href_lower for x in VALID_PATH_KEYWORDS):

                        to_visit.insert(0, href)

                    else:

                        to_visit.append(href)

            except Exception as e:

                print("Error crawling:", url, e)

        return pages