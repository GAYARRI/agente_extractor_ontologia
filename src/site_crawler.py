import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET


class SiteCrawler:

    def __init__(self, start_url, max_pages=100):

        self.start_url = start_url
        self.max_pages = max_pages

        parsed = urlparse(start_url)
        self.domain = parsed.netloc

        self.visited = set()
        self.queue = []

        # rutas candidatas cuando no hay sitemap
        self.auto_paths = [
            "",
            "agenda",
            "eventos",
            "rutas",
            "destinos",
            "experiencias",
            "playas",
            "mapa",
            "mapa-interactivo",
            "mapas-y-folletos",
            "que-no-te-lo-cuenten",
            "como-llegar",
            "donde-dormir",
            "donde-comer",
            "que-hacer",
            "que-visitar"
        ]


    # ---------------------------------------------------
    # normalizar URLs
    # ---------------------------------------------------

    def normalize_url(self, url):

        url = url.split("#")[0]
        url = url.rstrip("/")

        return url


    # ---------------------------------------------------
    # descarga página
    # ---------------------------------------------------

    def fetch(self, url):

        try:

            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                return None

            # ✅ corrección encoding
            html = response.content.decode("utf-8", errors="ignore")

            return html

        except Exception as e:

            print("Error descargando:", url, e)

            return None


    # ---------------------------------------------------
    # leer sitemap
    # ---------------------------------------------------

    def get_sitemap_links(self):

        sitemap_urls = [
            urljoin(self.start_url, "sitemap.xml"),
            urljoin(self.start_url, "sitemap_index.xml")
        ]

        links = []

        for sitemap in sitemap_urls:

            try:

                print(f"Buscando sitemap: {sitemap}")

                response = requests.get(sitemap, timeout=10)

                if response.status_code != 200:
                    continue

                root = ET.fromstring(response.text)

                for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):

                    url = self.normalize_url(loc.text)

                    links.append(url)

            except Exception as e:

                print(f"Error leyendo sitemap {sitemap}: {e}")

        print(f"Links encontrados en sitemap: {len(links)}")

        return links


    # ---------------------------------------------------
    # generar rutas automáticas
    # ---------------------------------------------------

    def generate_candidate_urls(self):

        candidates = []

        for path in self.auto_paths:

            url = urljoin(self.start_url, path)

            url = self.normalize_url(url)

            candidates.append(url)

        return candidates


    # ---------------------------------------------------
    # extraer enlaces internos
    # ---------------------------------------------------

    def extract_links(self, base_url, html):

        soup = BeautifulSoup(html, "html.parser")

        links = []

        for tag in soup.find_all("a", href=True):

            href = tag["href"]

            if href.startswith(("mailto:", "tel:", "javascript:")):
                continue

            full_url = urljoin(base_url, href)

            full_url = self.normalize_url(full_url)

            parsed = urlparse(full_url)

            # solo mismo dominio
            if parsed.netloc != self.domain:
                continue

            # evitar archivos
            if full_url.endswith((
                ".pdf",
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".svg",
                ".zip"
            )):
                continue

            links.append(full_url)

        return links


    # ---------------------------------------------------
    # crawler principal
    # ---------------------------------------------------

    def crawl(self, seed_urls=None):

        if seed_urls is None:
            seed_urls = [self.start_url]

        seed_urls = [self.normalize_url(u) for u in seed_urls]

        self.queue.extend(seed_urls)

        # intentar sitemap
        sitemap_links = self.get_sitemap_links()

        if sitemap_links:
            self.queue.extend(sitemap_links)
        else:
            print("Generando URLs candidatas...")
            self.queue.extend(self.generate_candidate_urls())

        pages = []

        while self.queue and len(self.visited) < self.max_pages:

            url = self.queue.pop(0)

            url = self.normalize_url(url)

            if url in self.visited:
                continue

            print(f"\n🌐 Procesando página {len(self.visited)+1}: {url}")

            html = self.fetch(url)

            if not html:
                continue

            print(f"   📄 HTML descargado: {len(html)} caracteres")

            pages.append((url, html))

            self.visited.add(url)

            links = self.extract_links(url, html)

            print(f"   🔎 Enlaces encontrados: {len(links)}")

            for link in links:

                if link not in self.visited and link not in self.queue:
                    self.queue.append(link)

        print(f"\nTotal páginas visitadas: {len(self.visited)}")

        return pages