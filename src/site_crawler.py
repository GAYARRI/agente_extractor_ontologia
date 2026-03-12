import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SiteCrawler:

    def __init__(self, start_url, max_pages=None):

        self.start_url = start_url
        self.max_pages = max_pages
        self.visited = set()

        parsed = urlparse(start_url)
        self.domain = parsed.netloc

        self.ignore_patterns = [
            "login",
            "search",
            "cookie",
            "privacy",
            "mailto:",
            "#"
        ]

    # --------------------------------------------------
    # limpiar texto
    # --------------------------------------------------

    def extract_text(self, html):

        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ")

        text = " ".join(text.split())

        return text

    # --------------------------------------------------
    # filtrar urls
    # --------------------------------------------------

    def is_valid_url(self, url):

        if any(p in url for p in self.ignore_patterns):
            return False

        parsed = urlparse(url)

        return parsed.netloc == self.domain

    # --------------------------------------------------
    # extraer links de HTML
    # --------------------------------------------------

    def extract_links(self, html, base_url):

        soup = BeautifulSoup(html, "html.parser")

        links = set()

        for a in soup.find_all("a", href=True):

            href = a["href"]

            url = urljoin(base_url, href)

            if self.is_valid_url(url):
                links.add(url)

        return links

    # --------------------------------------------------
    # leer sitemap
    # --------------------------------------------------

    def get_sitemap_links(self):

        sitemap_url = urljoin(self.start_url, "/sitemap.xml")

        print("Buscando sitemap:", sitemap_url)

        links = []

        try:

            response = requests.get(
                sitemap_url,
                verify=False,
                timeout=10
            )

            if response.status_code != 200:
                print("No se encontró sitemap")
                return []

            root = ET.fromstring(response.content)

            for loc in root.iter():

                if "loc" in loc.tag:
                    links.append(loc.text)

        except Exception as e:

            print("Error leyendo sitemap:", e)

        print("Links encontrados en sitemap:", len(links))

        return links

    # --------------------------------------------------
    # crawl principal
    # --------------------------------------------------

    def crawl_site(self):

        pages = []

        # primero intentar sitemap
        to_visit = self.get_sitemap_links()

        if not to_visit:
            to_visit = [self.start_url]

        while to_visit and (self.max_pages is None or len(pages) < self.max_pages):

            url = to_visit.pop(0)

            if url in self.visited:
                continue

            print("Crawling:", url)

            try:

                response = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    verify=False,
                    timeout=10
                )

                html = response.text

                text = self.extract_text(html)

                pages.append({
                    "url": url,
                    "html": html,
                    "text": text
                })

                links = self.extract_links(html, url)

                for link in links:

                    if link not in self.visited:
                        to_visit.append(link)

                self.visited.add(url)

            except Exception as e:

                print("Error crawling:", url, e)

        print("\nNúmero de páginas encontradas:", len(pages))

        return pages