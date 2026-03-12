import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import xml.etree.ElementTree as ET

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SiteCrawler:
    def __init__(self, max_pages=None, auto_paths=None):
        self.max_pages = max_pages
        self.visited = set()

        self.ignore_patterns = [
            "login",
            "search",
            "cookie",
            "privacy",
            "mailto:",
            "tel:",
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".svg",
            ".zip",
            ".xml",
        ]

        # rutas candidatas típicas en sitios turísticos
        self.auto_paths = auto_paths or [
            "playas",
            "naturaleza",
            "puertos-deportivos",
            "actividades-en-el-mar",
            "rutas-de-senderos",
            "cultura",
            "gastronomia",
            "golf",
            "alojamiento",
            "eventos",
            "ocio",
            "compras",
            "que-ver",
            "que-hacer",
            "experiencias",
            "lugares-de-interes",
            "monumentos",
            "museos",
            "restaurantes",
            "hoteles",
        ]

    # --------------------------------------------------
    # normalizar URL
    # --------------------------------------------------

    def normalize_url(self, url):
        if not url:
            return url

        parsed = urlparse(url)

        # quitamos query y fragment
        clean = parsed._replace(query="", fragment="")

        normalized = urlunparse(clean).rstrip("/")

        return normalized

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
    # dominio válido
    # --------------------------------------------------

    def is_valid_url(self, url, domain):
        if not url:
            return False

        url_lower = url.lower()

        if any(p in url_lower for p in self.ignore_patterns):
            return False

        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        domain = domain.lower()

        valid = (
            netloc == domain
            or netloc == f"www.{domain}"
            or domain == f"www.{netloc}"
        )

        return valid

    # --------------------------------------------------
    # enlaces generales
    # --------------------------------------------------

    def extract_links(self, html, base_url, domain):
        soup = BeautifulSoup(html, "html.parser")
        links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()

            if not href:
                continue

            url = urljoin(base_url, href)
            url = self.normalize_url(url)

            if self.is_valid_url(url, domain):
                links.add(url)

        return links

    # --------------------------------------------------
    # enlaces del menú / nav / footer / header
    # --------------------------------------------------

    def extract_menu_links(self, html, base_url, domain):
        soup = BeautifulSoup(html, "html.parser")
        links = set()

        containers = []
        containers.extend(soup.find_all("nav"))
        containers.extend(soup.find_all("menu"))
        containers.extend(soup.find_all("header"))
        containers.extend(soup.find_all("footer"))

        for container in containers:
            for a in container.find_all("a", href=True):
                href = a["href"].strip()

                if not href:
                    continue

                url = urljoin(base_url, href)
                url = self.normalize_url(url)

                if self.is_valid_url(url, domain):
                    links.add(url)

        return links

    # --------------------------------------------------
    # sitemap desde robots.txt
    # --------------------------------------------------

    def get_sitemaps_from_robots(self, start_url):
        robots_url = start_url.rstrip("/") + "/robots.txt"
        sitemaps = []

        print("Buscando robots.txt:", robots_url)

        try:
            response = requests.get(
                robots_url,
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
                timeout=15,
            )

            if response.status_code != 200:
                return []

            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding

            for line in response.text.splitlines():
                line = line.strip()

                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    if sitemap_url:
                        sitemaps.append(sitemap_url)

        except Exception as e:
            print("Error leyendo robots.txt:", e)

        return list(sorted(set(sitemaps)))

    # --------------------------------------------------
    # leer sitemap XML
    # --------------------------------------------------

    def parse_sitemap(self, sitemap_url, domain):
        links = []

        try:
            response = requests.get(
                sitemap_url,
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
                timeout=20,
            )

            if response.status_code != 200:
                return []

            root = ET.fromstring(response.content)

            for loc in root.iter():
                if "loc" in loc.tag and loc.text:
                    candidate = self.normalize_url(loc.text.strip())

                    if self.is_valid_url(candidate, domain):
                        links.append(candidate)

        except Exception as e:
            print(f"Error leyendo sitemap {sitemap_url}: {e}")

        return links

    # --------------------------------------------------
    # descubrir sitemaps
    # --------------------------------------------------

    def get_sitemap_links(self, start_url, domain):
        sitemap_candidates = []

        # 1) robots.txt
        robots_sitemaps = self.get_sitemaps_from_robots(start_url)
        if robots_sitemaps:
            print("Sitemaps detectados en robots.txt:")
            for s in robots_sitemaps:
                print(" -", s)
            sitemap_candidates.extend(robots_sitemaps)

        # 2) rutas clásicas
        sitemap_candidates.extend([
            urljoin(start_url, "/sitemap.xml"),
            urljoin(start_url, "/sitemap_index.xml"),
        ])

        links = []

        seen_sitemaps = set()
        for sitemap_url in sitemap_candidates:
            sitemap_url = self.normalize_url(sitemap_url)

            if sitemap_url in seen_sitemaps:
                continue

            seen_sitemaps.add(sitemap_url)

            print("Buscando sitemap:", sitemap_url)

            current_links = self.parse_sitemap(sitemap_url, domain)
            links.extend(current_links)

        links = sorted(set(links))
        print("Links encontrados en sitemap:", len(links))
        return links

    # --------------------------------------------------
    # generar rutas automáticas
    # --------------------------------------------------

    def generate_candidate_urls(self, start_url, domain):
        candidates = set()

        base = start_url.rstrip("/")

        for path in self.auto_paths:
            candidate = self.normalize_url(f"{base}/{path}")

            if self.is_valid_url(candidate, domain):
                candidates.add(candidate)

        return candidates

    # --------------------------------------------------
    # descargar página
    # --------------------------------------------------

    def fetch_page(self, url):
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            verify=False,
            timeout=20,
        )

        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding

        return response

    # --------------------------------------------------
    # crawl de un sitio
    # --------------------------------------------------

    def crawl_site(self, start_url):
        pages = []

        parsed = urlparse(start_url)
        domain = parsed.netloc.lower()

        # 1) sitemap
        to_visit = self.get_sitemap_links(start_url, domain)

        # 2) si no hay sitemap, empezar por home
        if not to_visit:
            to_visit = [self.normalize_url(start_url)]

        # 3) añadir rutas automáticas
        auto_candidates = self.generate_candidate_urls(start_url, domain)
        for url in auto_candidates:
            if url not in to_visit:
                to_visit.append(url)

        print("Total estimado inicial de páginas:", len(to_visit))

        while to_visit and (self.max_pages is None or len(pages) < self.max_pages):
            url = to_visit.pop(0)
            url = self.normalize_url(url)

            if url in self.visited:
                continue

            print(
                f"\nProgreso: visitadas={len(self.visited)} "
                f"pendientes={len(to_visit)} "
                f"extraídas={len(pages)}"
            )
            print("Crawling:", url)

            try:
                response = self.fetch_page(url)

                if response.status_code != 200:
                    self.visited.add(url)
                    continue

                html = response.text
                text = self.extract_text(html)

                pages.append(
                    {
                        "url": url,
                        "html": html,
                        "text": text,
                    }
                )

                # enlaces generales
                links = self.extract_links(html, url, domain)

                # enlaces de menú/nav/header/footer
                menu_links = self.extract_menu_links(html, url, domain)

                all_links = set()
                all_links.update(links)
                all_links.update(menu_links)

                for link in all_links:
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