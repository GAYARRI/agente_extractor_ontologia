import requests
from bs4 import BeautifulSoup


class TourismCrawler:

    def __init__(self, start_url, max_pages=5):

        self.start_url = start_url
        self.max_pages = max_pages


    def crawl(self):

        visited = set()
        to_visit = [self.start_url]

        pages = []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
            "Connection": "keep-alive"
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

                # evitar páginas bloqueadas
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

                    if href.startswith("/"):

                        href = self.start_url.rstrip("/") + href

                    if href.startswith(self.start_url) and href not in visited:

                        to_visit.append(href)

            except Exception as e:

                print("Error crawling:", url, e)

        return pages