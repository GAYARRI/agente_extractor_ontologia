import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from urllib.parse import unquote, urlparse, parse_qs
from src.utils.json_utils import safe_load_json


class TourismPropertyExtractor:
    """
    Extractor conservador de propiedades turísticas.

    Objetivos:
    - NO contaminar entidades con datos globales del portal/footer.
    - Priorizar texto local al bloque donde aparece la entidad.
    - Extraer solo propiedades con evidencia cercana a la entidad.
    - Mantener compatibilidad con TourismPipeline(): TourismPropertyExtractor()
      y extract(html, text, url, entity).
    """

    CONTACT_WINDOW = 280

    PORTAL_TEXT_BLOCKLIST = {
        "visita sevilla",
        "te queda mucho por descubrir",
        "te queda mucho por descubrir:",
        "estudiar en sevilla - visita sevilla",
        "el flamenco - visita sevilla",
    }

    GENERIC_IMAGE_FRAGMENTS = {
        "el-flamenco-bloque-2.jpg",
    }

    PERSON_CLASSES = {"Person"}
    NO_CONTACT_CLASSES = {"Person", "Concept", "Thing"}
    ALLOW_COORD_CLASSES = {
        "Place",
        "Location",
        "TouristAttraction",
        "Landmark",
        "Organization",
        "Service",
        "LocalBusiness",
    }

    ADDRESS_RE_LIST = [
        r"\b(?:calle|c/|avenida|avda\.?|plaza|paseo|alameda|alcalde|carretera|camino)\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\-\s]+",
        r"\b[A-Za-zÁÉÍÓÚÜÑáéíóúüñ\s]+,\s*\d{1,4}\b",
    ]

    PHONE_RE_LIST = [
        r"(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3}[\s\-]?\d{3}[\s\-]?\d{3}",
        r"(?:\+?\d{1,3}[\s\-]?)?\d{9}",
    ]

    EMAIL_RE = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

    def __init__(self):
        self._seen_coord_warnings = set()

    def _clean(self, text: str) -> str:
        text = text or ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _norm(self, text: str) -> str:
        return self._clean(text).lower()

    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        return self._clean(str(value))

    def _entity_name(self, entity: Dict[str, Any]) -> str:
        return (
            self._safe_str(entity.get("entity_name"))
            or self._safe_str(entity.get("entity"))
            or self._safe_str(entity.get("name"))
        )

    def _entity_class(self, entity: Dict[str, Any]) -> str:
        return self._safe_str(entity.get("class")) or "Thing"

    def _find_local_window(self, text: str, entity_name: str) -> str:
        text = self._clean(text)
        entity_name = self._clean(entity_name)
        if not text:
            return ""
        if not entity_name:
            return text[: self.CONTACT_WINDOW * 2]

        idx = text.lower().find(entity_name.lower())
        if idx == -1:
            return text[: self.CONTACT_WINDOW * 2]

        start = max(0, idx - self.CONTACT_WINDOW)
        end = min(len(text), idx + len(entity_name) + self.CONTACT_WINDOW)
        return text[start:end]

    def _contains_portal_noise(self, value: str) -> bool:
        v = self._norm(value)
        return not v or v in self.PORTAL_TEXT_BLOCKLIST

    def _extract_email(self, text: str) -> str:
        m = re.search(self.EMAIL_RE, text, flags=re.IGNORECASE)
        return m.group(0).strip() if m else ""

    def _extract_phone(self, text: str) -> str:
        for pattern in self.PHONE_RE_LIST:
            m = re.search(pattern, text)
            if m:
                value = m.group(0).strip()
                digits = re.sub(r"\D", "", value)
                if len(digits) >= 9:
                    return value
        return ""

    def _extract_address(self, text: str) -> str:
        for pattern in self.ADDRESS_RE_LIST:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                value = self._clean(m.group(0))
                if not self._contains_portal_noise(value):
                    return value
        return ""

    def _extract_hours(self, text: str) -> str:
        m = re.search(r"(\d{1,2}:\d{2})\s*[-–a]\s*(\d{1,2}:\d{2})", text, flags=re.IGNORECASE)
        return m.group(0).strip() if m else ""

    def _extract_price(self, text: str) -> str:
        m = re.search(r"(\d+[\.,]?\d*)\s?€", text)
        return m.group(0).strip() if m else ""

    def _extract_rating(self, text: str) -> str:
        m = re.search(r"([0-5](?:[\.,][0-9])?)\s*/\s*5", text)
        return m.group(1).replace(",", ".") if m else ""

    def _extract_coords_from_text(self, text: str) -> Dict[str, Any]:
        # lat/lon explícitos
        m = re.search(r"(?:lat|latitude)[\s:=]+([-0-9.]+).{0,25}(?:lon|lng|longitude)[\s:=]+([-0-9.]+)", text, flags=re.IGNORECASE)
        if m:
            try:
                return {"geoLat": float(m.group(1)), "geoLong": float(m.group(2))}
            except Exception:
                pass

        # formato @lat,lon de mapas
        m = re.search(r"@([-0-9.]+),([-0-9.]+)", text)
        if m:
            try:
                return {"geoLat": float(m.group(1)), "geoLong": float(m.group(2))}
            except Exception:
                pass

        # q=lat,lon
        m = re.search(r"q=([-0-9.]+),([-0-9.]+)", text)
        if m:
            try:
                return {"geoLat": float(m.group(1)), "geoLong": float(m.group(2))}
            except Exception:
                pass

        return {}

    def _extract_coords(self, html: str, local_text: str) -> Dict[str, Any]:
        html = html or ""
        for source in [local_text or "", html]:
            coords = self._extract_coords_from_text(source)
            if coords:
                return coords
        return {}

    def _img_src(self, img_tag, base_url: str) -> str:
        src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src") or ""
        src = self._safe_str(src)
        if not src:
            return ""
        return urljoin(base_url or "", src)

    def _image_is_generic(self, src: str) -> bool:
        src_l = (src or "").lower()
        return any(fragment in src_l for fragment in self.GENERIC_IMAGE_FRAGMENTS)

    def _find_candidate_images(self, soup: BeautifulSoup, entity_name: str, base_url: str) -> List[str]:
        entity_l = self._norm(entity_name)
        candidates = []

        for img in soup.find_all("img"):
            attrs_text = " ".join(
                filter(
                    None,
                    [
                        img.get("alt", ""),
                        img.get("title", ""),
                        img.get("aria-label", ""),
                        img.get("data-caption", ""),
                    ],
                )
            )
            attrs_l = self._norm(attrs_text)
            src = self._img_src(img, base_url)
            if not src or self._image_is_generic(src):
                continue

            if entity_l and entity_l in attrs_l:
                candidates.append(src)
                continue

            # padre/cercanía textual
            parent_text = self._norm(img.parent.get_text(" ", strip=True) if img.parent else "")
            if entity_l and entity_l in parent_text:
                candidates.append(src)

        # dedupe preservando orden
        out = []
        seen = set()
        for c in candidates:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _extract_entity_image(self, soup: BeautifulSoup, entity_name: str, base_url: str) -> str:
        candidates = self._find_candidate_images(soup, entity_name, base_url)
        return candidates[0] if candidates else ""

    def _extract_related_urls(self, soup: BeautifulSoup, entity_name: str, base_url: str) -> List[str]:
        entity_l = self._norm(entity_name)
        urls = []
        for a in soup.find_all("a", href=True):
            anchor_text = self._norm(a.get_text(" ", strip=True))
            href = self._safe_str(a.get("href"))
            if not href:
                continue
            if entity_l and entity_l in anchor_text:
                urls.append(urljoin(base_url or "", href))

        out = []
        seen = set()
        for u in urls:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def extract(self, entity, text="", html="", url=""):
        props = {}

        clean_text = (text or "").strip()
        if clean_text:
            props["description"] = clean_text[:300].strip()

        if url:
            props["url"] = url

        try:
            # 1️⃣ intentar extraer de HTML / JS
            coords, geo_debug = self.extract_best_coordinates(html=html, text=text)

            # 2️⃣ fallback por gazetteer (AQUÍ VA TU BLOQUE)
            if not coords and self._is_geographic_entity(entity, None):
                geo_hit = self._geo_from_gazetteer(entity)
                if geo_hit:
                    coords = {"lat": geo_hit["lat"], "lng": geo_hit["lng"]}
                    geo_debug = {"geo_source": geo_hit["source"]}

            # 3️⃣ guardar resultado
            if coords:
                coords = self._normalize_coords(coords.get("lat"), coords.get("lng"), source="best")
                props["coordinates"] = coords
                props["latitude"] = coords.get("lat")
                props["longitude"] = coords.get("lng")

            if geo_debug:
                props.setdefault("debug", {})
                props["debug"].update(geo_debug)

        except Exception as e:
            print(f"⚠️ GIS extraction error: {e}")

        props.setdefault("debug", {})
        props["debug"].update({
            "geo_available": bool(props.get("coordinates")),
            "has_description": bool(props.get("description")),
        })

        return props    
            
          
    
    def extract_from_jsonld(soup):
        scripts = soup.find_all("script", type="application/ld+json")
        coords = []

        for s in scripts:
            try:
                data = safe_load_json(s.string)
                if isinstance(data, dict):
                    geo = data.get("geo")
                    if geo:
                        lat = geo.get("latitude")
                        lon = geo.get("longitude")
                        if lat and lon:
                            coords.append((float(lat), float(lon)))
            except:
                continue

        return coords
    
    def extract_from_iframes(soup):
        coords = []
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", src)
            if match:
                coords.append((float(match.group(1)), float(match.group(2))))
        return coords
    

    def normalize_coords(lat, lon):
        lat = float(lat)
        lon = float(lon)

        # Detectar swap típico
        if abs(lat) > 90 and abs(lon) <= 90:
            lat, lon = lon, lat

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None

        return lat, lon
    

    def _to_float(self, value):
        try:
            if value is None or value == "":
                return None
            if isinstance(value, str):
                value = value.strip().replace(",", ".")
            return float(value)
        except Exception:
            return None


    def _normalize_coords(self, lat, lng, source: str = "unknown"):
        try:
            # soportar strings tipo "37,38"
            if isinstance(lat, str):
                lat = lat.replace(",", ".")
            if isinstance(lng, str):
                lng = lng.replace(",", ".")

            lat = float(lat)
            lng = float(lng)

        except (TypeError, ValueError):
            self._warn_invalid_coords("format", lat, lng, source)
            return None

        # validacion geografica
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            self._warn_invalid_coords("range", lat, lng, source)
            return None

        return {"lat": lat, "lng": lng}

    def _warn_invalid_coords(self, kind: str, lat, lng, source: str) -> None:
        key = (kind, str(lat), str(lng), source or "unknown")
        if key in self._seen_coord_warnings:
            return
        self._seen_coord_warnings.add(key)

        if kind == "format":
            print(f"Warning coords format [{source}]: lat={lat}, lng={lng}")
        elif kind == "range":
            print(f"Warning coords range [{source}]: lat={lat}, lng={lng}")


    def _extract_geo_from_jsonld(self, html: str):
        out = []
        if not html:
            return out

        pattern = re.compile(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.IGNORECASE | re.DOTALL
        )

        for block in pattern.findall(html):
            block = block.strip()
            if not block:
                continue

            try:
                data = safe_load_json(block)
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
                        out.append({
                            "lat": coords["lat"],
                            "lng": coords["lng"],
                            "source": "jsonld"
                        })

                for v in item.values():
                    if isinstance(v, (dict, list)):
                        stack.append(v)

        return out


    def _extract_geo_from_data_attrs(self, html: str):
        out = []
        if not html:
            return out

        patterns = [
            re.compile(
                r'data-lat=["\']([^"\']+)["\'][^>]*data-lng=["\']([^"\']+)["\']',
                re.IGNORECASE
            ),
            re.compile(
                r'data-lng=["\']([^"\']+)["\'][^>]*data-lat=["\']([^"\']+)["\']',
                re.IGNORECASE
            ),
        ]

        for idx, pattern in enumerate(patterns):
            for m in pattern.findall(html):
                if idx == 0:
                    lat, lng = m
                else:
                    lng, lat = m

                coords = self._normalize_coords(lat, lng, source="data-attrs")
                if coords:
                    out.append({
                        "lat": coords["lat"],
                        "lng": coords["lng"],
                        "source": "data-attrs"
                    })

        return out


    def _extract_geo_from_iframes(self, html: str):
        out = []
        if not html:
            return out

        iframe_srcs = re.findall(
            r'<iframe[^>]+src=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE
        )

        for src in iframe_srcs:
            src_decoded = unquote(src)

            # patrón @lat,lng
            m = re.search(r'@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)', src_decoded)
            if m:
                lat, lng = m.groups()
                coords = self._normalize_coords(lat, lng, source="iframe")
                if coords:
                    out.append({
                        "lat": coords["lat"],
                        "lng": coords["lng"],
                        "source": "iframe"
                    })
                    continue

            # q=lat,lng
            m = re.search(r'[?&]q=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)', src_decoded)
            if m:
                lat, lng = m.groups()
                coords = self._normalize_coords(lat, lng, source="iframe")
                if coords:
                    out.append({
                        "lat": coords["lat"],
                        "lng": coords["lng"],
                        "source": "iframe"
                    })

        return out


    def _extract_geo_from_text_regex(self, text: str):
        out = []
        if not text:
            return out

        patterns = [
            re.compile(r'@(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)'),
            re.compile(r'[?&]q=(-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)'),
            re.compile(r'lat(?:itude)?["\':=\s]+(-?\d+(?:\.\d+)?)', re.IGNORECASE),
            re.compile(r'(?:lng|lon|longitude)["\':=\s]+(-?\d+(?:\.\d+)?)', re.IGNORECASE),
        ]

        # pares directos
        for pattern in patterns[:2]:
            for m in pattern.findall(text):
                lat, lng = m
                coords = self._normalize_coords(lat, lng, source="regex")
                if coords:
                    out.append({
                        "lat": coords["lat"],
                        "lng": coords["lng"],
                        "source": "regex"
                    })

        # lat suelta + lon suelta
        lat_matches = patterns[2].findall(text)
        lon_matches = patterns[3].findall(text)

        if lat_matches and lon_matches:
            coords = self._normalize_coords(lat_matches[0], lon_matches[0], source="regex")
            if coords:
                out.append({
                    "lat": coords["lat"],
                    "lng": coords["lng"],
                    "source": "regex"
                })

        return out


    def _choose_best_geo_candidate(self, candidates):
        if not candidates:
            return None

        priority = {
            "jsonld": 4,
            "data-attrs": 3,
            "iframe": 2,
            "regex": 1,
        }

        cleaned = []
        seen = set()

        for c in candidates:
            if not c:
                continue

            lat = c.get("lat")
            lng = c.get("lng")
            src = c.get("source", "unknown")
            key = (round(lat, 6), round(lng, 6), src)

            if key in seen:
                continue
            seen.add(key)

            cleaned.append(c)

        cleaned.sort(key=lambda x: priority.get(x.get("source", ""), 0), reverse=True)
        return cleaned[0] if cleaned else None


    def extract_best_coordinates(self, html: str = "", text: str = ""):
        candidates = []
        candidates.extend(self._extract_geo_from_jsonld(html))
        candidates.extend(self._extract_geo_from_data_attrs(html))
        candidates.extend(self._extract_geo_from_iframes(html))
        candidates.extend(self._extract_geo_from_text_regex(html or text))

        best = self._choose_best_geo_candidate(candidates)
        if not best:
            return {}, {}

        coords = {
            "lat": best["lat"],
            "lng": best["lng"]
        }
        debug = {
            "geo_source": best.get("source", "unknown")
        }
        return coords, debug
    
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
            for m in pattern.findall(html):
                lat, lng = m
                coords = self._normalize_coords(lat, lng, source="map-js")
                if coords:
                    out.append({
                        "lat": coords["lat"],
                        "lng": coords["lng"],
                        "source": "map-js"
                    })

        return out
    
    def _is_geographic_entity(self, entity_name: str, entity_class=None) -> bool:
        cls = str(entity_class or "").lower()
        geo_markers = ["place", "location", "tourismdestination", "city", "municipality", "neighborhood", "district"]
        return any(x in cls for x in geo_markers)
