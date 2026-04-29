from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


DEFAULT_HEADERS = {
    "User-Agent": "TourismOntologyAgent/1.0",
}


def normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="").geturl()


def strip_www(domain: str) -> str:
    domain = (domain or "").strip().lower()
    return domain[4:] if domain.startswith("www.") else domain


def same_domain(url: str, base_domain: str) -> bool:
    return strip_www(urlparse(url).netloc) == strip_www(base_domain)


def normalize_scope_path(path: str) -> str:
    value = (path or "/").strip()
    if not value or value == "/":
        return "/"
    value = "/" + value.strip("/")
    return value.rstrip("/")


def same_scope(url: str, base_domain: str, base_path_prefix: str) -> bool:
    if not same_domain(url, base_domain):
        return False
    if base_path_prefix == "/":
        return True
    path = normalize_scope_path(urlparse(url).path or "/")
    return path == base_path_prefix or path.startswith(base_path_prefix + "/")


def fetch_text(url: str, timeout: int) -> tuple[str | None, str | None]:
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response.text, response.url
    except requests.RequestException:
        return None, None


def discover_sitemaps(start_url: str, timeout: int) -> list[str]:
    sitemaps: list[str] = []
    normalized_start = normalize_url(start_url)
    parsed = urlparse(normalized_start)
    root = f"{parsed.scheme}://{parsed.netloc}/"

    robots_url = urljoin(root, "/robots.txt")
    robots_text, _ = fetch_text(robots_url, timeout=timeout)
    if robots_text:
        for raw_line in robots_text.splitlines():
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.strip().lower() == "sitemap":
                sitemap_url = normalize_url(value.strip())
                if sitemap_url and sitemap_url not in sitemaps:
                    sitemaps.append(sitemap_url)

    default_sitemap = normalize_url(urljoin(root, "/sitemap.xml"))
    if default_sitemap and default_sitemap not in sitemaps:
        sitemaps.append(default_sitemap)

    return sitemaps


def count_sitemap_urls(start_url: str, timeout: int = 20, max_sitemaps: int = 200) -> dict[str, Any]:
    normalized_start = normalize_url(start_url)
    parsed_start = urlparse(normalized_start)
    base_domain = parsed_start.netloc.lower()
    base_path_prefix = normalize_scope_path(parsed_start.path or "/")
    sitemap_queue = deque(discover_sitemaps(normalized_start, timeout=timeout))
    seen_sitemaps: set[str] = set()
    unique_urls: set[str] = set()
    sitemap_stats: list[dict[str, Any]] = []

    while sitemap_queue and len(seen_sitemaps) < max_sitemaps:
        sitemap_url = normalize_url(sitemap_queue.popleft())
        if not sitemap_url or sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)

        xml_text, resolved_url = fetch_text(sitemap_url, timeout=timeout)
        if not xml_text:
            sitemap_stats.append(
                {"sitemap": sitemap_url, "status": "unreachable", "url_count": 0}
            )
            continue

        effective_url = normalize_url(resolved_url or sitemap_url)
        soup = BeautifulSoup(xml_text, "xml")
        loc_nodes = soup.find_all("loc")
        url_count_before = len(unique_urls)
        child_sitemaps = 0

        for loc in loc_nodes:
            loc_url = normalize_url(loc.get_text(strip=True))
            if not loc_url:
                continue
            if loc_url.endswith(".xml"):
                if loc_url not in seen_sitemaps:
                    sitemap_queue.append(loc_url)
                    child_sitemaps += 1
                continue
            if same_scope(loc_url, base_domain, base_path_prefix):
                unique_urls.add(loc_url)

        sitemap_stats.append(
            {
                "sitemap": effective_url,
                "status": "ok",
                "new_url_count": len(unique_urls) - url_count_before,
                "child_sitemaps": child_sitemaps,
            }
        )

    return {
        "start_url": normalized_start,
        "domain": base_domain,
        "scope_prefix": base_path_prefix,
        "sitemaps_discovered": list(seen_sitemaps),
        "sitemap_count": len(seen_sitemaps),
        "unique_url_count": len(unique_urls),
        "all_urls": sorted(unique_urls),
        "sample_urls": sorted(unique_urls)[:25],
        "sitemap_stats": sitemap_stats,
    }


def group_urls_by_prefix(urls: list[str], depth: int = 1, top: int = 25) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()

    for url in urls:
        path = urlparse(url).path.strip("/")
        segments = [segment for segment in path.split("/") if segment]
        if not segments:
            prefix = "/"
        else:
            prefix = "/" + "/".join(segments[:depth])
        counter[prefix] += 1

    grouped = []
    for prefix, count in counter.most_common(top):
        grouped.append({"prefix": prefix, "count": count})
    return grouped


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate site size from robots.txt and sitemaps")
    parser.add_argument("--start_url", required=True, help="Site URL to inspect")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    parser.add_argument("--max_sitemaps", type=int, default=200, help="Maximum sitemap files to inspect")
    parser.add_argument("--prefix_depth", type=int, default=1, help="Path depth used to group URLs by prefix")
    parser.add_argument("--top_prefixes", type=int, default=25, help="Number of top prefixes to show")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    result = count_sitemap_urls(
        start_url=args.start_url,
        timeout=args.timeout,
        max_sitemaps=args.max_sitemaps,
    )
    result["top_prefixes"] = group_urls_by_prefix(
        result.get("all_urls", []),
        depth=max(1, args.prefix_depth),
        top=max(1, args.top_prefixes),
    )

    if args.json:
        result.pop("all_urls", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Start URL: {result['start_url']}")
    print(f"Domain: {result['domain']}")
    print(f"Scope prefix: {result['scope_prefix']}")
    print(f"Sitemaps processed: {result['sitemap_count']}")
    print(f"Unique same-domain URLs found: {result['unique_url_count']}")
    print(f"Top prefixes (depth={max(1, args.prefix_depth)}):")
    for item in result["top_prefixes"]:
        print(f"  - {item['prefix']}: {item['count']}")
    print("Sample URLs:")
    for url in result["sample_urls"][:10]:
        print(f"  - {url}")


if __name__ == "__main__":
    main()
