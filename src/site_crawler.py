import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class SiteCrawler:
    def __init__(self, start_url, max_pages=50):
        self.start_url = start_url
        self.max_pages = max_pages
        self.visited = set()
        self.to_visit = [start_url]
        self.allowed_domain = urlparse(start_url).hostname

    def clean_url(self, url):
        return url.split("?")[0].split("#")[0]

    def is_same_domain(self, url):
        host = urlparse(url).hostname
        return host == self.allowed_domain

    def is_valid_url(self, url):
        if not url:
            return False

        # Solo permitir URLs del dominio principal exacto
        if not self.is_same_domain(url):
            return False

        # Evitar archivos no HTML
        if any(url.lower().endswith(ext) for ext in [
            ".jpg", ".jpeg", ".png", ".gif", ".webp",
            ".pdf", ".svg", ".zip", ".xml", ".doc", ".docx",
            ".xls", ".xlsx", ".ppt", ".pptx"
        ]):
            return False

        # Evitar URLs problemáticas o irrelevantes
        if any(x in url.lower() for x in [
            "author", "login", "register", "review=",
            "service=", "wp-json", "feed", "mailto:",
            "tel:", "javascript:"
        ]):
            return False

        return True

    def crawl(self):
        pages = []

        while self.to_visit and len(pages) < self.max_pages:
            url = self.to_visit.pop(0)
            clean = self.clean_url(url)

            if clean in self.visited:
                continue

            if not self.is_valid_url(clean):
                continue

            print(f"\nProcesando página {len(pages) + 1}: {clean}")

            try:
                headers = {
                    "User-Agent": "Mozilla/5.0"
                }
                response = requests.get(clean, headers=headers, timeout=10)

                if response.status_code != 200:
                    print(f"⚠️ Estado no válido para {clean}: {response.status_code}")
                    continue

                # Validar también la URL final por si hay redirección externa
                final_url = self.clean_url(response.url)
                if not self.is_same_domain(final_url):
                    print(f"⚠️ Redirección fuera del dominio ignorada: {final_url}")
                    continue

                html = response.content.decode("utf-8", errors="ignore")

                pages.append((final_url, html))
                self.visited.add(final_url)

                soup = BeautifulSoup(html, "html.parser")

                for link in soup.find_all("a", href=True):
                    href = link.get("href")
                    full_url = self.clean_url(urljoin(final_url, href))

                    if (
                        full_url not in self.visited
                        and full_url not in self.to_visit
                        and self.is_valid_url(full_url)
                    ):
                        self.to_visit.append(full_url)

            except Exception as e:
                print(f"❌ Error descargando {clean}: {e}")

        return pages