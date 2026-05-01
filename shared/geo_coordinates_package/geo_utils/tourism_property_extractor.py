import re
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

from .json_utils import safe_load_json


class TourismPropertyExtractor:
    def __init__(self):
        self._seen_coord_warnings = set()

    def _normalize_coords(self, lat, lng, source: str = "unknown"):
        try:
            if isinstance(lat, str):
                lat = lat.replace(",", ".")
            if isinstance(lng, str):
                lng = lng.replace(",", ".")
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            self._warn_invalid_coords("format", lat, lng, source)
            return None

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            self._warn_invalid_coords("range", lat, lng, source)
            return None

        return {"lat": lat, "lng": lng}

    def _warn_invalid_coords(self, kind: str, lat, lng, source: str) -> None:
        key = (kind, str(lat), str(lng), source or "unknown")
        if key in self._seen_coord_warnings:
            return
        self._seen_coord_warnings.add(key)

    def _coords_plausible_for_url(self, coords: Dict[str, Any], url: str = "") -> bool:
        if not isinstance(coords, dict):
            return False
        lat = coords.get("lat")
        lng = coords.get("lng")
        if lat is None or lng is None:
            return False

        host = (urlparse(url or "").netloc or "").lower()
        if host.endswith(".es") or ".es:" in host:
            if not (27.0 <= float(lat) <= 44.5 and -18.5 <= float(lng) <= 5.5):
                self._warn_invalid_coords("range", lat, lng, source="context")
                return False
        return True

    def _extract_geo_from_jsonld(self, html: str):
        out = []
        if not html:
            return out

        pattern = re.compile(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.IGNORECASE | re.DOTALL,
        )

        for block in pattern.findall(html):
            try:
                data = safe_load_json(block.strip())
            except Exception:
                continue

            stack = [data]
            while stack:
                item = stack.pop()
                if isinstance(item, list):
                    stack.extend(item)
                    continue
                if not isinstance(item, dict):
                    continue

                geo = item.get("geo")
                if isinstance(geo, dict):
                    coords = self._normalize_coords(
                        geo.get("latitude"),
                        geo.get("longitude"),
                        source="jsonld",
                    )
                    if coords:
                        out.append({"lat": coords["lat"], "lng": coords["lng"], "source": "jsonld"})

                for value in item.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)
        return out

    def _extract_geo_from_data_attrs(self, html: str):
        out = []
        if not html:
            return out

        patterns = [
            re.compile(r'data-lat=["\']([^"\']+)["\'][^>]*data-lng=["\']([^"\']+)["\']', re.IGNORECASE),
            re.compile(r'data-lng=["\']([^"\']+)["\'][^>]*data-lat=["\']([^"\']+)["\']', re.IGNORECASE),
        ]

        for idx, pattern in enumerate(patterns):
            for match in pattern.findall(html):
                if idx == 0:
                    lat, lng = match
                else:
                    lng, lat = match
                coords = self._normalize_coords(lat, lng, source="data-attrs")
                if coords:
                    out.append({"lat": coords["lat"], "lng": coords["lng"], "source": "data-attrs"})
        return out

    def _extract_geo_from_iframes(self, html: str):
        out = []
        if not html:
            return out

        iframe_srcs = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        for src in iframe_srcs:
            src_decoded = unquote(src)
            for pattern in [
                r'@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)',
                r'[?&]q=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)',
            ]:
                match = re.search(pattern, src_decoded)
                if not match:
                    continue
                lat, lng = match.groups()
                coords = self._normalize_coords(lat, lng, source="iframe")
                if coords:
                    out.append({"lat": coords["lat"], "lng": coords["lng"], "source": "iframe"})
                    break
        return out

    def _extract_geo_from_map_js(self, html: str):
        out = []
        if not html:
            return out

        patterns = [
            re.compile(r'L\.marker\(\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]\s*\)'),
            re.compile(r'LatLng\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)'),
            re.compile(r'["\']lat["\']\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*["\'](?:lng|lon|longitude)["\']\s*:\s*(-?\d+(?:\.\d+)?)', re.IGNORECASE),
            re.compile(r'["\']latitude["\']\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*["\']longitude["\']\s*:\s*(-?\d+(?:\.\d+)?)', re.IGNORECASE),
        ]

        for pattern in patterns:
            for lat, lng in pattern.findall(html):
                coords = self._normalize_coords(lat, lng, source="map-js")
                if coords:
                    out.append({"lat": coords["lat"], "lng": coords["lng"], "source": "map-js"})
        return out

    def _extract_geo_from_text_regex(self, text: str):
        out = []
        if not text:
            return out

        direct_patterns = [
            re.compile(r'@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)'),
            re.compile(r'[?&]q=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)'),
        ]
        paired_patterns = [
            re.compile(r'(?:lat|latitude)\b["\':=\s]*(-?\d+(?:\.\d+)?).{0,80}?(?:lng|lon|longitude)\b["\':=\s]*(-?\d+(?:\.\d+)?)', re.IGNORECASE | re.DOTALL),
            re.compile(r'(?:lng|lon|longitude)\b["\':=\s]*(-?\d+(?:\.\d+)?).{0,80}?(?:lat|latitude)\b["\':=\s]*(-?\d+(?:\.\d+)?)', re.IGNORECASE | re.DOTALL),
        ]

        for pattern in direct_patterns:
            for lat, lng in pattern.findall(text):
                coords = self._normalize_coords(lat, lng, source="regex")
                if coords:
                    out.append({"lat": coords["lat"], "lng": coords["lng"], "source": "regex"})

        for idx, pattern in enumerate(paired_patterns):
            for match in pattern.findall(text):
                if idx == 0:
                    lat, lng = match
                else:
                    lng, lat = match
                coords = self._normalize_coords(lat, lng, source="regex")
                if coords:
                    out.append({"lat": coords["lat"], "lng": coords["lng"], "source": "regex"})
        return out

    def _choose_best_geo_candidate(self, candidates: List[Dict[str, Any]]):
        if not candidates:
            return None

        priority = {"jsonld": 5, "data-attrs": 4, "iframe": 3, "map-js": 2, "regex": 1}
        cleaned = []
        seen = set()
        for item in candidates:
            key = (round(item["lat"], 6), round(item["lng"], 6), item.get("source", "unknown"))
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(item)

        cleaned.sort(key=lambda x: priority.get(x.get("source", ""), 0), reverse=True)
        return cleaned[0]

    def extract_best_coordinates(self, html: str = "", text: str = ""):
        candidates: List[Dict[str, Any]] = []
        candidates.extend(self._extract_geo_from_jsonld(html))
        candidates.extend(self._extract_geo_from_data_attrs(html))
        candidates.extend(self._extract_geo_from_iframes(html))
        candidates.extend(self._extract_geo_from_map_js(html))
        candidates.extend(self._extract_geo_from_text_regex(html or text))

        best = self._choose_best_geo_candidate(candidates)
        if not best:
            return {}, {}

        return (
            {"lat": best["lat"], "lng": best["lng"]},
            {"geo_source": best.get("source", "unknown")},
        )

    def extract(self, entity, text="", html="", url=""):
        props: Dict[str, Any] = {}
        coords, debug = self.extract_best_coordinates(html=html, text=text)
        if coords:
            coords = self._normalize_coords(coords.get("lat"), coords.get("lng"), source="best")
            if coords and self._coords_plausible_for_url(coords, url):
                props["coordinates"] = coords
                props["latitude"] = coords["lat"]
                props["longitude"] = coords["lng"]
            elif coords:
                debug = dict(debug or {})
                debug["geo_rejected"] = "outside_expected_region"

        if debug:
            props["debug"] = debug
        return props
