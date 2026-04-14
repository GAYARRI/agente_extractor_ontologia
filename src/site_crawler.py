from __future__ import annotations

import time
from collections import deque
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.exceptions import RequestException, SSLError, Timeout

# Suprime warnings cuando verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SiteCrawler:
    def __init__(self, start_url: str, max_pages: int = 10, timeout: int = 30):
        self.start_url = start_url
        self.max_pages = max_pages
        self.timeout = timeout

        self.visited: Set[str] = set()
        self.to_visit = deque([start_url])

        parsed = urlparse(start_url)
        self.allowed_domain = parsed.netloc.lower()

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            }
        )

        # Dominios con SSL roto para los que ya decidimos usar verify=False
        self.insecure_domains: Set[str] = set()

    # =========================================================
    # API pública
    # =========================================================

    def crawl(self) -> List[Tuple[str, str]]:
        pages: List[Tuple[str, str]] = []

        while self.to_visit and len(pages) < self.max_pages:
            url = self.to_visit.popleft()

            normalized_url = self._normalize_url(url)
            if not normalized_url or normalized_url in self.visited:
                continue

            self.visited.add(normalized_url)

            print(f"🌐 Visitando: {normalized_url}")

            html = self._fetch(normalized_url)
            if not html:
                continue

            pages.append((normalized_url, html))

            for link in self._extract_links(normalized_url, html):
                if link not in self.visited:
                    self.to_visit.append(link)

            time.sleep(0.2)

        return pages

    # =========================================================
    # Fetch robusto con fallback SSL
    # =========================================================

    def _fetch(self, url: str) -> str | None:
        domain = urlparse(url).netloc.lower()

        # Si ya sabemos que este dominio tiene SSL roto, ir directo con verify=False
        if domain in self.insecure_domains:
            return self._request(url, verify=False)

        # Primer intento normal
        try:
            return self._request(url, verify=True)

        except SSLError:
            print(f"⚠️ SSL inválido en {url}, desactivando verificación para este dominio...")
            self.insecure_domains.add(domain)

            try:
                return self._request(url, verify=False)
            except Exception as e:
                print(f"⚠️ Error procesando {url}: {e}")
                return None

        except Exception as e:
            print(f"⚠️ Error procesando {url}: {e}")
            return None

    def _request(self, url: str, verify: bool) -> str:
        response = self.session.get(
            url,
            timeout=self.timeout,
            verify=verify,
            allow_redirects=True,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        return response.text

    # =========================================================
    # Links
    # =========================================================

    def _extract_links(self, base_url: str, html: str) -> List[str]:
        links: List[str] = []

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            return links

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href:
                continue

            absolute = urljoin(base_url, href)
            absolute = self._normalize_url(absolute)

            if not absolute:
                continue

            if not self._is_same_domain(absolute):
                continue

            if self._should_skip_url(absolute):
                continue

            links.append(absolute)

        return self._dedupe(links)

    # =========================================================
    # URL helpers
    # =========================================================

    def _normalize_url(self, url: str) -> str:
        if not url:
            return ""

        try:
            parsed = urlparse(url)
        except Exception:
            return ""

        if parsed.scheme not in {"http", "https"}:
            return ""

        clean = parsed._replace(fragment="", params="", query="")
        normalized = clean.geturl().rstrip("/")

        return normalized

    def _is_same_domain(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return domain == self.allowed_domain

    def _should_skip_url(self, url: str) -> bool:
        low = url.lower()

        bad_extensions = (
            ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
            ".pdf", ".zip", ".rar", ".7z", ".mp4", ".mp3",
            ".avi", ".mov", ".wmv", ".doc", ".docx", ".xls", ".xlsx",
        )

        if low.endswith(bad_extensions):
            return True

        bad_fragments = [
            "/tag/",
            "/author/",
            "/feed",
            "mailto:",
            "tel:",
            "javascript:",
            "#",
        ]

        return any(fragment in low for fragment in bad_fragments)

    def _dedupe(self, urls: List[str]) -> List[str]:
        seen = set()
        out = []

        for url in urls:
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(url)

        return out