import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class SiteCrawler:

    def __init__(self, start_url, max_pages=50):

        self.start_url = start_url
        self.max_pages = max_pages

        self.visited = set()
        self.to_visit = [start_url]

    # ==================================================
    # LIMPIAR URL (QUITAR PARAMS)
    # ==================================================

    def clean_url(self, url):
        return url.split("?")[0]

    # ==================================================
    # FILTRO DE URLS
    # ==================================================

    def is_valid_url(self, url):

        if not url:
            return False

        # evitar anchors
        if "#" in url:
            return False

        # evitar archivos
        if any(url.endswith(ext) for ext in [".jpg", ".png", ".pdf"]):
            return False

        # 🔥 evitar loops típicos
        if any(x in url for x in [
            "author",
            "login",
            "register",
            "review=",
            "service=",
            "wp-json",
            "feed"
        ]):
            return False

        return True

    # ==================================================
    # CRAWL
    # ==================================================

    def crawl(self):

        pages = []

        while self.to_visit and len(pages) < self.max_pages:

            url = self.to_visit.pop(0)
            clean = self.clean_url(url)

            # 🔥 permitir SIEMPRE la URL inicial
            if clean != self.start_url:
                if clean in self.visited:
                    continue

                if not self.is_valid_url(clean):
                    continue

            print(f"\n🌐 Procesando página {len(pages)+1}: {clean}")

            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(clean, headers=headers, timeout=10)

                if response.status_code != 200:
                    continue

                html = response.content.decode("utf-8", errors="ignore")

                # 🔥 AÑADIR SIEMPRE
                pages.append((clean, html))

                self.visited.add(clean)

                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")

                for link in soup.find_all("a", href=True):

                    href = link.get("href")
                    full_url = urljoin(clean, href)
                    full_url = self.clean_url(full_url)

                    # 🔥 evitar duplicados y basura
                    if full_url not in self.visited and self.is_valid_url(full_url):
                        self.to_visit.append(full_url)

            except Exception as e:
                print(f"❌ Error descargando {clean}: {e}")

        return pages