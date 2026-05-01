from __future__ import annotations

import re
import time
from collections import deque
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup


class SiteCrawler:
    def __init__(self, start_url: str, max_pages: int = 10, timeout: int = 20):
        self.raw_start_url = (start_url or "").strip()
        self.start_url = self.raw_start_url.rstrip("/")
        self.max_pages = max_pages or 10
        self.timeout = timeout
        self.default_request_delay = 0.6
        self.blocked_language_prefixes = {
            "de",
            "en",
            "fr",
            "it",
            "pt",
            "ja",
            "ko",
            "zh",
            "zh-hans",
            "zh-hant",
        }

        parsed = urlparse(self.start_url)
        self.base_domain = parsed.netloc.lower()
        self.base_path_prefix = self._normalize_scope_path(parsed.path or "/")
        self.allowed_domains: Set[str] = set()
        if self.base_domain:
            bare_domain = self._strip_www(self.base_domain)
            self.allowed_domains.add(self.base_domain)
            if bare_domain:
                self.allowed_domains.add(bare_domain)
                self.allowed_domains.add(f"www.{bare_domain}")

        self.headers = {
            "User-Agent": "TourismOntologyAgent/1.0"
        }

        # Si un dominio falla por SSL una vez, seguimos sin verify para ese dominio
        self.insecure_domains: Set[str] = set()
        self.domain_request_delay: dict[str, float] = {}
        self.domain_last_request_ts: dict[str, float] = {}

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def crawl(self) -> List[Tuple[str, str]]:
        """
        Devuelve una lista de tuplas (url, html).
        Tolera errores HTTP puntuales sin romper todo el crawl.
        """
        results: List[Tuple[str, str]] = []
        visited: Set[str] = set()
        successful_urls: Set[str] = set()
        queue = deque(self._build_start_candidates())

        while queue and len(results) < self.max_pages:
            current_url = queue.popleft()
            if not current_url or current_url in visited:
                continue

            visited.add(current_url)

            print(f"Visitando: {current_url}")
            html, resolved_url = self._fetch(current_url)

            # Si falla la descarga, se omite y seguimos
            if not html:
                continue

            effective_url = self._normalize_url(resolved_url or current_url) or current_url
            if effective_url in successful_urls:
                continue
            visited.add(effective_url)
            self._register_domain(effective_url)
            results.append((effective_url, html))
            successful_urls.add(effective_url)

            # Extraer enlaces y seguir crawling
            try:
                discovered_links = self._extract_links(effective_url, html)
                priority_links = []
                regular_links = []
                for link in discovered_links:
                    if link in visited or link in queue:
                        continue
                    if self._is_priority_detail_link(effective_url, link):
                        priority_links.append(link)
                    else:
                        regular_links.append(link)

                for link in reversed(priority_links):
                    queue.appendleft(link)
                for link in regular_links:
                    queue.append(link)
            except Exception as e:
                print(f"Error extrayendo enlaces desde {effective_url}: {e}")

        return results

    # ------------------------------------------------------------------
    # Descarga
    # ------------------------------------------------------------------

    def _fetch(self, url: str) -> tuple[str | None, str]:
        """
        Descarga una URL.
        - Si hay SSL invalido, reintenta sin verificacion para el dominio.
        - Si hay HTTPError (404, 403, ...), devuelve None y sigue.
        """
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        verify_ssl = domain not in self.insecure_domains

        try:
            return self._request(url, verify=verify_ssl)

        except requests.exceptions.SSLError:
            print(f"SSL invalido en {url}, desactivando verificacion para este dominio...")
            self.insecure_domains.add(domain)

            try:
                return self._request(url, verify=False)
            except requests.exceptions.HTTPError as e:
                return self._handle_http_error(url, e, verify=False)
            except requests.exceptions.RequestException as e:
                print(f"Error de red en {url}: {e}")
                return None, url
            except Exception as e:
                print(f"Error inesperado al descargar {url}: {e}")
                return None, url

        except requests.exceptions.HTTPError as e:
            return self._handle_http_error(url, e, verify=verify_ssl)

        except requests.exceptions.RequestException as e:
            print(f"Error de red en {url}: {e}")
            return None, url

        except Exception as e:
            print(f"Error inesperado al descargar {url}: {e}")
            return None, url

    def _request(self, url: str, verify: bool = True) -> tuple[str, str]:
        self._respect_crawl_delay(url)
        response = requests.get(
            url,
            headers=self.headers,
            timeout=self.timeout,
            verify=verify,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response.text, response.url

    def _respect_crawl_delay(self, url: str) -> None:
        domain = urlparse(url).netloc.lower()
        if not domain:
            return

        delay = self.domain_request_delay.get(domain, self.default_request_delay)
        last_ts = self.domain_last_request_ts.get(domain, 0.0)
        wait_seconds = delay - (time.time() - last_ts)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self.domain_last_request_ts[domain] = time.time()

    def _register_crawl_delay(self, domain: str, robots_text: str) -> None:
        domain = (domain or "").strip().lower()
        if not domain or not robots_text:
            return

        matched_delay = None
        active_user_agent = None

        for raw_line in robots_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                active_user_agent = value.lower()
                continue

            if key == "crawl-delay" and active_user_agent in {"*", self.headers["User-Agent"].lower()}:
                try:
                    parsed_delay = float(value)
                    if parsed_delay > 0:
                        matched_delay = parsed_delay
                except ValueError:
                    pass

        if matched_delay is not None:
            self.domain_request_delay[domain] = max(self.default_request_delay, matched_delay)

    def _handle_http_error(
        self,
        url: str,
        error: requests.exceptions.HTTPError,
        verify: bool,
    ) -> tuple[str | None, str]:
        status = getattr(error.response, "status_code", None)

        for fallback_url in self._fallback_urls_for_error(url, status):
            if fallback_url == url:
                continue
            try:
                print(f"HTTP {status} en {url}, probando alternativa: {fallback_url}")
                return self._request(fallback_url, verify=verify)
            except requests.exceptions.HTTPError:
                continue
            except requests.exceptions.RequestException:
                continue

        print(f"HTTP {status} en {url}, se omite.")
        return None, url

    # ------------------------------------------------------------------
    # Enlaces
    # ------------------------------------------------------------------

    def _extract_links(self, current_url: str, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []

        for a in soup.find_all("a", href=True):
            self._append_candidate_link(links, current_url, a.get("href"))

        for tag in soup.find_all(True):
            for attr in ("data-href", "data-url", "data-link", "data-path", "href"):
                value = tag.get(attr)
                if value:
                    self._append_candidate_link(links, current_url, value)

            onclick = tag.get("onclick")
            if onclick:
                for match in re.findall(r"""['"](/[^'"]+)['"]""", onclick):
                    self._append_candidate_link(links, current_url, match)

        for raw_link in self._extract_links_from_raw_html(html):
            self._append_candidate_link(links, current_url, raw_link)

        # dedupe preserve order
        deduped = []
        seen = set()
        for link in links:
            if link not in seen:
                seen.add(link)
                deduped.append(link)

        return deduped

    def _append_candidate_link(self, links: List[str], current_url: str, raw_href: str | None) -> None:
        href = (raw_href or "").strip()
        if not href:
            return

        # Saltar anclas, mailto, tel, javascript
        if href.startswith("#"):
            return
        if href.startswith("mailto:") or href.startswith("tel:") or href.startswith("javascript:"):
            return

        absolute = urljoin(current_url, href)
        normalized = self._normalize_url(absolute)

        if not normalized:
            return
        if not self._is_same_domain(normalized):
            return
        if not self._is_in_allowed_scope(normalized):
            return
        if self._should_skip_url(normalized):
            return

        links.append(normalized)

    def _extract_links_from_raw_html(self, html: str) -> List[str]:
        if not html:
            return []

        candidates: List[str] = []
        patterns = [
            r'''"(?:href|url|as|canonical)"\s*:\s*"([^"#][^"]*)"''',
            r"""'(?:href|url|as|canonical)'\s*:\s*'([^'#][^']*)'""",
        ]

        for pattern in patterns:
            for match in re.findall(pattern, html):
                value = (match or "").strip()
                if self._looks_like_plausible_raw_link(value) and value not in candidates:
                    candidates.append(value)

        return candidates

    def _looks_like_plausible_raw_link(self, value: str) -> bool:
        value = (value or "").strip()
        if not value:
            return False

        # Evita tokens internos del frontend que suelen producir URLs truncadas.
        if value.startswith("{") or value.startswith("["):
            return False
        if " " in value:
            return False

        parsed = urlparse(value)
        path = parsed.path if parsed.scheme else value
        if not path.startswith("/"):
            return False

        path = path.strip("/")
        if not path:
            return False

        segments = [segment for segment in path.split("/") if segment]
        if len(segments) < 2:
            return False

        # Finales sospechosos que suelen venir de slugs cortados.
        suspicious_tails = {
            "em",
            "en",
            "os",
            "as",
            "do",
            "da",
            "de",
            "del",
            "para",
            "pela",
            "por",
        }
        if segments[-1].lower() in suspicious_tails:
            return False

        return True

    # ------------------------------------------------------------------
    # Normalizacion / filtros
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
        return netloc in self.allowed_domains

    def _is_in_allowed_scope(self, url: str) -> bool:
        parsed = urlparse(url)
        path = self._normalize_scope_path(parsed.path or "/")
        if self.base_path_prefix == "/":
            return True
        return path == self.base_path_prefix or path.startswith(self.base_path_prefix + "/")

    def _should_skip_url(self, url: str) -> bool:
        low = url.lower()
        parsed = urlparse(url)
        path_low = (parsed.path or "").lower()
        query_low = (parsed.query or "").lower()
        path_segments = [segment for segment in (parsed.path or "/").split("/") if segment]

        # Evitar versiones del sitio en otros idiomas para no duplicar ruido
        if path_segments:
            first_segment = path_segments[0].lower()
            if (
                first_segment in self.blocked_language_prefixes
                or any(first_segment.startswith(prefix + "-") for prefix in self.blocked_language_prefixes)
            ):
                return True

        # Evitar archivos binarios/medios
        bad_exts = [
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
            ".pdf", ".zip", ".rar", ".7z",
            ".mp4", ".mp3", ".avi", ".mov", ".wmv",
            ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            ".xml", ".json", ".css", ".js",
        ]
        if any(path_low.endswith(ext) for ext in bad_exts):
            return True

        # Evitar algunos endpoints comunes poco utiles para crawling semantico
        bad_fragments = [
            "/wp-content/",
            "/wp-json/",
            "/feed",
            "/tag/",
            "/author/",
            "/search?",
            "/documents/",
            "/documentos/",
            "/o/",
            "/c/",
            "?s=",
            "/cdn-cgi/",
        ]
        if any(fragment in low for fragment in bad_fragments):
            return True

        bad_query_markers = [
            "minifiertype=css",
            "minifiertype=js",
            "themeid=",
            "browserid=",
            "languageid=",
        ]
        if any(marker in query_low for marker in bad_query_markers):
            return True

        return False

    def _build_start_candidates(self) -> List[str]:
        candidates: List[str] = []
        for candidate in self._fallback_urls_for_error(self.raw_start_url or self.start_url, status_code=None):
            normalized = self._normalize_url(candidate)
            if normalized and self._is_in_allowed_scope(normalized) and normalized not in candidates:
                candidates.append(normalized)
        for candidate in self._discover_seed_urls(candidates):
            normalized = self._normalize_url(candidate)
            if normalized and self._is_in_allowed_scope(normalized) and normalized not in candidates:
                candidates.append(normalized)
        return candidates

    def _fallback_urls_for_error(self, url: str, status_code: int | None) -> List[str]:
        normalized = self._normalize_url(url)
        if not normalized:
            return []

        parsed = urlparse(normalized)
        host = parsed.netloc.lower()
        path = parsed.path or "/"
        fallback_urls = [normalized]

        is_root = path == "/"
        should_try_host_variants = is_root and (status_code is None or status_code == 404)

        if should_try_host_variants:
            bare_host = self._strip_www(host)
            for variant in [bare_host, f"www.{bare_host}" if bare_host else ""]:
                if not variant:
                    continue
                fallback = urlunparse((
                    parsed.scheme,
                    variant,
                    "/",
                    parsed.params,
                    parsed.query,
                    "",
                ))
                normalized_fallback = self._normalize_url(fallback)
                if normalized_fallback and normalized_fallback not in fallback_urls:
                    fallback_urls.append(normalized_fallback)

        return fallback_urls

    def _register_domain(self, url: str) -> None:
        netloc = urlparse(url).netloc.lower()
        if not netloc:
            return

        self.base_domain = netloc
        self.allowed_domains.add(netloc)

        bare_domain = self._strip_www(netloc)
        if bare_domain:
            self.allowed_domains.add(bare_domain)
            self.allowed_domains.add(f"www.{bare_domain}")

    def _strip_www(self, domain: str) -> str:
        domain = (domain or "").strip().lower()
        if domain.startswith("www."):
            return domain[4:]
        return domain

    def _discover_seed_urls(self, base_candidates: List[str]) -> List[str]:
        seeds: List[str] = []
        sitemap_urls: List[str] = []

        for base_url in base_candidates:
            parsed = urlparse(base_url)
            host_root = urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))

            robots_url = urljoin(host_root, "/robots.txt")
            robots_text, _ = self._fetch(robots_url)
            if robots_text:
                self._register_crawl_delay(parsed.netloc, robots_text)
                for line in robots_text.splitlines():
                    line = line.strip()
                    if not line or ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    if key.strip().lower() == "sitemap":
                        sitemap_candidate = self._normalize_url(value.strip())
                        if sitemap_candidate and sitemap_candidate not in sitemap_urls:
                            sitemap_urls.append(sitemap_candidate)

            default_sitemap = urljoin(host_root, "/sitemap.xml")
            default_sitemap = self._normalize_url(default_sitemap)
            if default_sitemap and default_sitemap not in sitemap_urls:
                sitemap_urls.append(default_sitemap)

            for seed in self._extract_urls_from_sitemaps(sitemap_urls):
                if seed not in seeds:
                    seeds.append(seed)

            for fallback_path in [
                "/agenda",
                "/disfruta",
                "/que-ver",
                "/ven",
                "/evento",
                "/noticias",
                "/profesionales",
            ]:
                fallback_url = self._normalize_url(urljoin(host_root, fallback_path))
                if fallback_url and self._is_in_allowed_scope(fallback_url) and fallback_url not in seeds:
                    seeds.append(fallback_url)

        return seeds[: max(self.max_pages * 4, 20)]

    def _extract_urls_from_sitemaps(self, sitemap_urls: List[str]) -> List[str]:
        extracted: List[str] = []
        seen_sitemaps: Set[str] = set()
        pending = deque(sitemap_urls)

        while pending and len(extracted) < max(self.max_pages * 6, 50):
            sitemap_url = self._normalize_url(pending.popleft())
            if not sitemap_url or sitemap_url in seen_sitemaps:
                continue
            seen_sitemaps.add(sitemap_url)

            xml_text, resolved_url = self._fetch(sitemap_url)
            effective_sitemap = self._normalize_url(resolved_url or sitemap_url) or sitemap_url
            if not xml_text:
                continue

            try:
                soup = BeautifulSoup(xml_text, "xml")
            except Exception:
                continue

            for loc in soup.find_all("loc"):
                loc_url = self._normalize_url((loc.get_text() or "").strip())
                if not loc_url:
                    continue
                if loc_url.endswith(".xml"):
                    if loc_url not in seen_sitemaps:
                        pending.append(loc_url)
                    continue
                if not self._is_same_domain_or_alias(loc_url, effective_sitemap):
                    continue
                if not self._is_in_allowed_scope(loc_url):
                    continue
                if self._should_skip_url(loc_url):
                    continue
                if loc_url not in extracted:
                    extracted.append(loc_url)
                if len(extracted) >= max(self.max_pages * 6, 50):
                    break

        return extracted

    def _is_same_domain_or_alias(self, url: str, reference_url: str) -> bool:
        ref_host = urlparse(reference_url).netloc.lower()
        url_host = urlparse(url).netloc.lower()
        if not ref_host or not url_host:
            return False
        return self._strip_www(ref_host) == self._strip_www(url_host)

    def _normalize_scope_path(self, path: str) -> str:
        value = (path or "/").strip()
        if not value or value == "/":
            return "/"
        value = "/" + value.strip("/")
        return value.rstrip("/")

    def _is_priority_detail_link(self, current_url: str, link_url: str) -> bool:
        current_path = (urlparse(current_url).path or "/").strip("/")
        link_path = (urlparse(link_url).path or "/").strip("/")
        if not link_path or link_path == current_path:
            return False

        current_segments = [segment for segment in current_path.split("/") if segment]
        link_segments = [segment for segment in link_path.split("/") if segment]

        listing_roots = {
            "que-ver",
            "agenda",
            "disfruta",
            "ven",
            "evento",
            "noticias",
            "profesionales",
        }
        generic_sections = listing_roots | {"blog", "category", "tag", "search"}

        current_is_listing = (
            not current_segments
            or current_segments[-1].lower() in listing_roots
            or len(current_segments) == 1
        )
        if not current_is_listing:
            return False

        if len(link_segments) <= len(current_segments):
            return False

        if link_segments[-1].lower() in generic_sections:
            return False

        if any(segment.lower() in generic_sections for segment in link_segments[:-1]):
            return True

        return len(link_segments) >= 2
