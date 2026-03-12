import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SiteCrawler:

    def __init__(self, max_pages=None):

        self.max_pages = max_pages
        self.visited = set()

        self.ignore_patterns = [
            "login",
            "search",
            "cookie",
            "privacy",
            "mailto:",
            "#",
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".svg",
            ".zip",
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

    def is_valid_url(self, url, domain):

        if not url:
            return False

        if any(p in url.lower() for p in self.ignore_patterns):
            return False

        parsed = urlparse(url)

        return parsed.netloc == domain

    # --------------------------------------------------
    # extraer links de HTML
    # --------------------------------------------------

    def extract_links(self, html, base_url, domain):

        soup = BeautifulSoup(html, "html.parser")

        links = set()

        for a in soup.find_all("a", href=True):

            href = a["href"]

            url = urljoin(base_url, href)

            url = url.split("#")[0]

            if self.is_valid_url(url, domain):
                links.add(url)

        return links

    # --------------------------------------------------
    # leer sitemap
    # --------------------------------------------------

    def get_sitemap_links(self, start_url, domain):

        sitemap_url = urljoin(start_url, "/sitemap.xml")

        print("Buscando sitemap:", sitemap_url)

        links = []

        try:

            response = requests.get(
                sitemap_url,
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
                timeout=10
            )

            if response.status_code != 200:
                print("No se encontró sitemap")
                return []

            root = ET.fromstring(response.content)

            for loc in root.iter():

                if "loc" in loc.tag and loc.text:

                    if self.is_valid_url(loc.text, domain):
                        links.append(loc.text)

        except Exception as e:

            print("Error leyendo sitemap:", e)

        print("Links encontrados en sitemap:", len(links))

        return links

    # --------------------------------------------------
    # crawl de un sitio
    # --------------------------------------------------

    def crawl_site(self, start_url):

        pages = []

        parsed = urlparse(start_url)
        domain = parsed.netloc

        to_visit = self.get_sitemap_links(start_url, domain)

        if not to_visit:
            to_visit = [start_url]

        total_estimated = len(to_visit)

        print("Total estimado de páginas:", total_estimated)

        while to_visit and (self.max_pages is None or len(pages) < self.max_pages):

            url = to_visit.pop(0)

            if url in self.visited:
                continue

            print(
                f"\nProgreso: visitadas={len(self.visited)} "
                f"pendientes={len(to_visit)} "
                f"extraídas={len(pages)}"
            )

            print("Crawling:", url)

            try:

                response = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    verify=False,
                    timeout=10
                )

                if response.status_code != 200:
                    self.visited.add(url)
                    continue

                html = response.text

                text = self.extract_text(html)

                pages.append({
                    "url": url,
                    "html": html,
                    "text": text
                })

                links = self.extract_links(html, url, domain)

                for link in links:

                    if link not in self.visited and link not in to_visit:
                        to_visit.append(link)

                self.visited.add(url)

            except Exception as e:

                print("Error crawling:", url, e)

                self.visited.add(url)

        print(f"\nNúmero de páginas encontradas en {start_url}: {len(pages)}")

        return pages

    # --------------------------------------------------
    # crawl principal para lista de seeds
    # --------------------------------------------------

    def crawl(self, seed_urls):

        all_pages = []

        for start_url in seed_urls:

            self.visited = set()

            pages = self.crawl_site(start_url)

            all_pages.extend(pages)

        print(f"\nTotal páginas recuperadas: {len(all_pages)}")

        return all_pages