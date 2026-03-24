from urllib.parse import urljoin, urlparse, urldefrag
import requests
from requests.exceptions import SSLError
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SiteCrawler:
    BLOCKED_LANGUAGES = {"en", "fr", "it", "de"}

    def __init__(self, start_url, max_pages=50):
        self.start_url = start_url
        self.max_pages = max_pages
        self.visited = set()
        self.allowed_domain = urlparse(start_url).hostname
        self.verify_ssl = True
        self.session = requests.Session()

    def clean_url(self, url):
        url, _ = urldefrag(url)
        return url.rstrip("/")

    def is_same_domain(self, url):
        host = urlparse(url).hostname
        return host == self.allowed_domain

    def is_blocked_language_url(self, url):
        path = urlparse(url).path.lower().strip("/")
        if not path:
            return False

        first_segment = path.split("/")[0]

        return (
            first_segment in self.BLOCKED_LANGUAGES
            or any(first_segment.startswith(f"{lang}-") for lang in self.BLOCKED_LANGUAGES)
        )

    def is_valid_url(self, url):
        if not url:
            return False

        if self.is_blocked_language_url(url):
            return False

        if not self.is_same_domain(url):
            return False

        if any(url.lower().endswith(ext) for ext in [
            ".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf",
            ".zip", ".rar", ".doc", ".docx", ".xls", ".xlsx"
        ]):
            return False

        return True

    def extract_links(self, html, base_url):
        soup = BeautifulSoup(html, "html.parser")
        links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(base_url, href)
            full_url = self.clean_url(full_url)

            if self.is_valid_url(full_url) and full_url not in self.visited:
                links.add(full_url)

        return links

    def fetch_url(self, url, headers):
        try:
            return self.session.get(
                url,
                timeout=10,
                headers=headers,
                allow_redirects=True,
                verify=self.verify_ssl
            )
        except SSLError:
            if self.verify_ssl:
                print(f"⚠️ SSL inválido en {url}, desactivando verificación para este dominio...")
                self.verify_ssl = False
                return self.session.get(
                    url,
                    timeout=10,
                    headers=headers,
                    allow_redirects=True,
                    verify=False
                )
            raise

    def crawl(self):
        to_visit = [self.clean_url(self.start_url)]
        pages = []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        while to_visit and len(self.visited) < self.max_pages:
            current = to_visit.pop(0)
            clean = self.clean_url(current)

            if clean in self.visited:
                continue

            if not self.is_valid_url(clean):
                continue

            self.visited.add(clean)

            try:
                print(f"🌐 Visitando: {clean}")
                response = self.fetch_url(clean, headers)

                if response.status_code >= 400:
                    print(f"⚠️ Estado no válido para {clean}: {response.status_code}")
                    continue

                final_url = self.clean_url(response.url)

                if not self.is_same_domain(final_url):
                    print(f"⚠️ Redirección fuera del dominio ignorada: {final_url}")
                    continue

                if self.is_blocked_language_url(final_url):
                    print(f"⚠️ Redirección a idioma bloqueado ignorada: {final_url}")
                    continue

                html = response.content.decode("utf-8", errors="ignore")
                pages.append((final_url, html))

                new_links = self.extract_links(html, final_url)
                to_visit.extend(link for link in new_links if link not in self.visited)

            except Exception as e:
                print(f"❌ Error descargando {clean}: {e}")

        return pages