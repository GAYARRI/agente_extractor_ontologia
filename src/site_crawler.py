from __future__ import annotations

import time
from collections import deque
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


class SiteCrawler:
    def __init__(self, start_url: str, max_pages: int = 10, timeout: int = 20):
        self.start_url = start_url.rstrip("/")
        self.max_pages = max_pages
        self.timeout = timeout
        self.blocked_language_prefixes = {
            "de",
            "en",
            "fr",
            "it",
            "pt",
        }

        parsed = urlparse(self.start_url)
        self.base_domain = parsed.netloc.lower()

        self.headers = {
            "User-Agent": "TourismOntologyAgent/1.0"
        }

        # Si un dominio falla por SSL una vez, seguimos sin verify para ese dominio
        self.insecure_domains: Set[str] = set()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def crawl(self) -> List[Tuple[str, str]]:
        """
        Devuelve una lista de tuplas (url, html).
        Tolera errores HTTP puntuales sin romper todo el crawl.
        """
        results: List[Tuple[str, str]] = []
        visited: Set[str] = set()
        queue = deque([self._normalize_url(self.start_url)])

        while queue and len(results) < self.max_pages:
            current_url = queue.popleft()
            if not current_url or current_url in visited:
                continue

            visited.add(current_url)

            print(f"🌐 Visitando: {current_url}")
            html = self._fetch(current_url)

            # Si falla la descarga, se omite y seguimos
            if not html:
                continue

            results.append((current_url, html))

            # Extraer enlaces y seguir crawling
            try:
                for link in self._extract_links(current_url, html):
                    if link not in visited and link not in queue:
                        queue.append(link)
            except Exception as e:
                print(f"⚠️ Error extrayendo enlaces desde {current_url}: {e}")

            # Pequeña pausa amable para no machacar el servidor
            time.sleep(0.15)

        return results

    # ------------------------------------------------------------------
    # Descarga
    # ------------------------------------------------------------------

    def _fetch(self, url: str) -> str | None:
        """
        Descarga una URL.
        - Si hay SSL inválido, reintenta sin verificación para el dominio.
        - Si hay HTTPError (404, 403, ...), devuelve None y sigue.
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        verify_ssl = domain not in self.insecure_domains

        try:
            return self._request(url, verify=verify_ssl)

        except requests.exceptions.SSLError:
            print(f"⚠️ SSL inválido en {url}, desactivando verificación para este dominio...")
            self.insecure_domains.add(domain)

            try:
                return self._request(url, verify=False)
            except requests.exceptions.HTTPError as e:
                status = getattr(e.response, "status_code", None)
                print(f"⚠️ HTTP {status} en {url}, se omite.")
                return None
            except requests.exceptions.RequestException as e:
                print(f"⚠️ Error de red en {url}: {e}")
                return None
            except Exception as e:
                print(f"⚠️ Error inesperado al descargar {url}: {e}")
                return None

        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            print(f"⚠️ HTTP {status} en {url}, se omite.")
            return None

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Error de red en {url}: {e}")
            return None

        except Exception as e:
            print(f"⚠️ Error inesperado al descargar {url}: {e}")
            return None

    def _request(self, url: str, verify: bool = True) -> str:
        response = requests.get(
            url,
            headers=self.headers,
            timeout=self.timeout,
            verify=verify,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response.text

    # ------------------------------------------------------------------
    # Enlaces
    # ------------------------------------------------------------------

    def _extract_links(self, current_url: str, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href:
                continue

            # Saltar anclas, mailto, tel, javascript
            if href.startswith("#"):
                continue
            if href.startswith("mailto:") or href.startswith("tel:") or href.startswith("javascript:"):
                continue

            absolute = urljoin(current_url, href)
            normalized = self._normalize_url(absolute)

            if not normalized:
                continue
            if not self._is_same_domain(normalized):
                continue
            if self._should_skip_url(normalized):
                continue

            links.append(normalized)

        # dedupe preserve order
        deduped = []
        seen = set()
        for link in links:
            if link not in seen:
                seen.add(link)
                deduped.append(link)

        return deduped

    # ------------------------------------------------------------------
    # Normalización / filtros
    # ------------------------------------------------------------------

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""

        parsed = urlparse(url)

        # Solo http/https
        if parsed.scheme not in ("http", "https"):
            return ""

        # Quitar fragmentos
        parsed = parsed._replace(fragment="")

        # Normalizar path
        path = parsed.path or "/"
        path = path.replace("//", "/")

        # Quitar trailing slash excepto root
        if path != "/":
            path = path.rstrip("/")

        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            path,
            parsed.params,
            parsed.query,
            "",
        ))

        return normalized

    def _is_same_domain(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        return netloc == self.base_domain

    def _should_skip_url(self, url: str) -> bool:
        low = url.lower()
        parsed = urlparse(url)
        path_segments = [segment for segment in (parsed.path or "/").split("/") if segment]

        # Evitar versiones del sitio en otros idiomas para no duplicar ruido
        if path_segments:
            first_segment = path_segments[0].lower()
            if first_segment in self.blocked_language_prefixes:
                return True

        # Evitar archivos binarios/medios
        bad_exts = [
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
            ".pdf", ".zip", ".rar", ".7z",
            ".mp4", ".mp3", ".avi", ".mov", ".wmv",
            ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            ".xml", ".json",
        ]
        if any(low.endswith(ext) for ext in bad_exts):
            return True

        # Evitar algunos endpoints comunes poco útiles para crawling semántico
        bad_fragments = [
            "/wp-content/",
            "/wp-json/",
            "/feed",
            "/tag/",
            "/author/",
            "/search?",
            "?s=",
            "/cdn-cgi/",
        ]
        if any(fragment in low for fragment in bad_fragments):
            return True

        return False
