import os
import certifi
import requests

from firecrawl import Firecrawl

from src.site_crawler import SiteCrawler


class FirecrawlClient:
    def __init__(self, api_key=None, fallback_max_pages=50):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self.fallback_max_pages = fallback_max_pages
        self.client = None

        # forzar certifi para requests / ssl
        os.environ["SSL_CERT_FILE"] = certifi.where()
        os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

        if self.api_key:
            try:
                self.client = Firecrawl(api_key=self.api_key)
            except Exception as e:
                print(f"[WARN] No se pudo inicializar Firecrawl: {e}")
                self.client = None
        else:
            print("[WARN] FIRECRAWL_API_KEY no encontrada. Se usará fallback con SiteCrawler.")

    def _fallback_crawl(self, url, limit):
        print("[INFO] Activando fallback con SiteCrawler...")

        crawler = SiteCrawler(max_pages=limit or self.fallback_max_pages)
        pages = crawler.crawl([url])

        # emular estructura parecida a Firecrawl
        class FallbackResult:
            def __init__(self, data):
                self.data = data

        data = []
        for page in pages:
            data.append(
                {
                    "metadata": {
                        "sourceURL": page.get("url", "")
                    },
                    "html": page.get("html", ""),
                    "markdown": page.get("text", ""),
                }
            )

        return FallbackResult(data)

    def map_site(self, url, limit=100):
        if not self.client:
            print("[WARN] Firecrawl no disponible. map_site no soportado en fallback.")
            return {"links": [url]}

        try:
            return self.client.map(url=url, limit=limit)
        except Exception as e:
            print(f"[WARN] Error en Firecrawl map_site: {e}")
            return {"links": [url]}

    def crawl_site(self, url, limit=50, sitemap="include"):
        if not self.client:
            return self._fallback_crawl(url, limit)

        try:
            return self.client.crawl(
                url=url,
                limit=limit,
                sitemap=sitemap,
                poll_interval=1,
                timeout=120,
            )

        except requests.exceptions.SSLError as e:
            print(f"[WARN] Error SSL en Firecrawl: {e}")
            return self._fallback_crawl(url, limit)

        except requests.exceptions.RequestException as e:
            print(f"[WARN] Error de red en Firecrawl: {e}")
            return self._fallback_crawl(url, limit)

        except Exception as e:
            print(f"[WARN] Error general en Firecrawl crawl_site: {e}")
            return self._fallback_crawl(url, limit)

    def scrape_page(self, url):
        if not self.client:
            print("[WARN] Firecrawl no disponible. scrape_page no soportado en fallback.")
            return None

        try:
            return self.client.scrape(
                url,
                formats=["markdown", "html"]
            )
        except Exception as e:
            print(f"[WARN] Error en Firecrawl scrape_page: {e}")
            return None