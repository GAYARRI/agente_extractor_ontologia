import json
import re
import os
from urllib.parse import urljoin, urlparse, urlunparse, unquote

from bs4 import BeautifulSoup


class TourismPropertyExtractor:
    def __init__(self, properties=None):
        if properties is None:
            properties = [
                "name",
                "description",
                "address",
                "telephone",
                "url",
                "relatedUrls",
                "contactUrls",
                "latitude",
                "longitude",
                "openingHours",
                "image",
                "mainImage",
                "additionalImages",
            ]
        self.properties = properties

    # --------------------------------------------------
    # helpers
    # --------------------------------------------------
    def _normalize(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _normalize_image_url(self, url):
        if not url:
            return None

        url = url.strip()
        if not url:
            return None

        parsed = urlparse(url)

        clean = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            "",
            ""
        ))

        return unquote(clean)

    def _image_signature(self, url):
        if not url:
            return None

        norm = self._normalize_image_url(url)
        if not norm:
            return None

        path = unquote(urlparse(norm).path).lower()
        filename = os.path.basename(path)

        if not filename:
            return path

        thumb_prefixes = [
            "120px-", "150px-", "180px-", "200px-", "220px-", "250px-",
            "300px-", "320px-", "400px-", "500px-", "640px-", "800px-",
            "1024px-"
        ]

        for prefix in thumb_prefixes:
            if filename.startswith(prefix):
                filename = filename[len(prefix):]
                break

        return filename

    def _dedupe_images(self, images):
        result = []
        seen = set()

        for img in images:
            norm = self._normalize_image_url(img)
            sig = self._image_signature(norm)

            if not norm or not sig:
                continue

            if sig in seen:
                continue

            seen.add(sig)
            result.append(norm)

        return result

    def _matches_entity(self, entity: str, candidate: str) -> bool:
        if not entity or not candidate:
            return False
        e = self._normalize(entity)
        c = self._normalize(candidate)
        return e == c or e in c or c in e

    def _clean_text(self, text: str) -> str:
        return " ".join((text or "").strip().split())

    def _add_unique(self, container, value):
        if value is None:
            return
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return
        if value not in container:
            container.append(value)

    def _abs_url(self, base_url, maybe_url):
        if not maybe_url:
            return None
        return urljoin(base_url, maybe_url.strip())

    def _same_domain(self, base_url, other_url):
        try:
            return urlparse(base_url).netloc == urlparse(other_url).netloc
        except Exception:
            return False

    def _clean_phone(self, phone):
        if not phone:
            return None
        phone = phone.replace("tel:", "").strip()
        phone = re.sub(r"\s+", " ", phone)
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 9:
            return phone
        if len(digits) == 11 and digits.startswith("34"):
            return phone
        return None

    def _extract_postal_address(self, address_obj):
        if isinstance(address_obj, str):
            return self._clean_text(address_obj)

        if not isinstance(address_obj, dict):
            return None

        parts = [
            address_obj.get("streetAddress"),
            address_obj.get("addressLocality"),
            address_obj.get("addressRegion"),
            address_obj.get("postalCode"),
            address_obj.get("addressCountry"),
        ]
        parts = [self._clean_text(p) for p in parts if p]
        return ", ".join(parts) if parts else None

    def _extract_image_values(self, image_value, base_url):
        images = []

        if isinstance(image_value, str):
            self._add_unique(images, self._abs_url(base_url, image_value))

        elif isinstance(image_value, list):
            for item in image_value:
                if isinstance(item, str):
                    self._add_unique(images, self._abs_url(base_url, item))
                elif isinstance(item, dict):
                    self._add_unique(images, self._abs_url(base_url, item.get("url")))

        elif isinstance(image_value, dict):
            self._add_unique(images, self._abs_url(base_url, image_value.get("url")))
            self._add_unique(images, self._abs_url(base_url, image_value.get("contentUrl")))

        return images

    def _is_probably_logo(self, url):
        if not url:
            return False
        value = url.lower()
        return any(x in value for x in ["logo", "icon", "sprite", "avatar"])

    def _is_contact_url(self, url):
        if not url:
            return False
        value = url.lower()
        return any(
            x in value
            for x in [
                "/contact",
                "/contacto",
                "/reserv",
                "/booking",
                "/book",
                "mailto:",
                "tel:",
                "google.com/maps",
                "maps.app.goo.gl",
                "goo.gl/maps",
                "whatsapp",
            ]
        )

    # --------------------------------------------------
    # block extraction
    # --------------------------------------------------
    def extract_blocks(self, soup, page_url=""):
        blocks = []
        candidates = soup.find_all(["section", "article", "div", "li"])

        for node in candidates:
            text = self._clean_text(node.get_text(" ", strip=True))
            if len(text) < 60:
                continue

            heading_tag = node.find(["h1", "h2", "h3", "h4"])
            heading = self._clean_text(heading_tag.get_text(" ", strip=True)) if heading_tag else ""

            img = node.find("img")
            image = None
            if img:
                image = img.get("src") or img.get("data-src") or img.get("srcset")
                if image and "," in image and " " in image:
                    image = image.split(",")[0].strip().split(" ")[0]
                image = self._abs_url(page_url, image)

            blocks.append(
                {
                    "heading": heading,
                    "text": text,
                    "image": image,
                    "node": node,
                    "page_url": page_url,
                }
            )

        return blocks

    def score_block_for_entity(self, block, entity):
        score = 0.0
        entity_n = self._normalize(entity)
        heading_n = self._normalize(block.get("heading", ""))
        text_n = self._normalize(block.get("text", ""))

        if heading_n:
            if entity_n == heading_n:
                score += 1.0
            elif entity_n in heading_n or heading_n in entity_n:
                score += 0.7

        if entity_n in text_n:
            score += 0.4

        collective_patterns = [
            "desde ",
            "hasta ",
            "entre ",
            "como ",
            "rincones ",
            "playas vírgenes",
            "playas naturales",
            "playas virgenes",
        ]
        if any(p in text_n for p in collective_patterns):
            score -= 0.3

        return score

    def find_best_block_for_entity(self, soup, entity, page_url=""):
        blocks = self.extract_blocks(soup, page_url=page_url)
        if not blocks:
            return None

        best_block = None
        best_score = -999

        for block in blocks:
            score = self.score_block_for_entity(block, entity)
            if score > best_score:
                best_score = score
                best_block = block

        if best_score < 0.35:
            return None

        return best_block

    # --------------------------------------------------
    # JSON-LD extraction
    # --------------------------------------------------
    def extract_jsonld(self, soup):
        results = []
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            try:
                raw = script.string or script.get_text(strip=True)
                if not raw:
                    continue

                data = json.loads(raw)

                if isinstance(data, dict):
                    if "@graph" in data and isinstance(data["@graph"], list):
                        results.extend(data["@graph"])
                    else:
                        results.append(data)
                elif isinstance(data, list):
                    results.extend(data)
            except Exception:
                continue

        return results

    # --------------------------------------------------
    # meta
    # --------------------------------------------------
    def extract_meta(self, soup, page_url=""):
        props = {}

        for meta in soup.find_all("meta"):
            prop = meta.get("property") or meta.get("name")
            content = meta.get("content")

            if not content:
                continue

            if prop == "og:title":
                props["name"] = content.strip()

            elif prop == "og:description":
                props["description"] = content.strip()

            elif prop == "description" and "description" not in props:
                props["description"] = content.strip()

            elif prop == "og:image":
                props["image"] = self._abs_url(page_url, content.strip())

            elif prop == "twitter:image" and "image" not in props:
                props["image"] = self._abs_url(page_url, content.strip())

            elif prop in ("og:url", "twitter:url"):
                props["url"] = self._abs_url(page_url, content.strip())

        return props

    # --------------------------------------------------
    # fallback extraction
    # --------------------------------------------------
    def extract_geo(self, text):
        geo = {}

        latlon = re.search(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", text or "")
        if latlon:
            geo["latitude"] = latlon.group(1)
            geo["longitude"] = latlon.group(2)

        return geo

    def extract_phone(self, text):
        if not text:
            return None

        matches = re.findall(r"(?:\+34\s*)?(?:\(?\d{2,3}\)?[\s\-]*){3,5}", text)
        for match in matches:
            phone = self._clean_phone(match)
            if phone:
                return phone

        return None

    def extract_address_from_text(self, text):
        if not text:
            return None

        patterns = [
            r"(?:dirección|address)\s*[:\-]\s*([^.|\n]+)",
            r"(?:calle|c\/|avenida|avda\.?|plaza|paseo)\s+([^.|\n]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                address = self._clean_text(match.group(1))
                if len(address) > 8:
                    return address

        return None

    def clean_description_text(self, text: str) -> str:
        if not text:
            return ""

        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

        noise_lines = [
            "watch later",
            "share",
            "copy link",
            "youtube",
            "subscribers",
            "ver video",
            "photo image",
            "wtm teaser not sub",
        ]

        lines = []
        for line in text.splitlines():
            clean_line = line.strip()
            if not clean_line:
                continue
            if any(n in clean_line.lower() for n in noise_lines):
                continue
            lines.append(clean_line)

        text = " ".join(lines)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # --------------------------------------------------
    # links and images
    # --------------------------------------------------
    def extract_links_from_node(self, node, page_url):
        related_urls = []
        contact_urls = []

        if not node:
            return related_urls, contact_urls

        for a in node.find_all("a", href=True):
            href = a.get("href", "").strip()
            abs_href = self._abs_url(page_url, href)

            if not abs_href:
                continue

            if href.startswith("#"):
                continue

            if abs_href == page_url:
                continue

            if self._same_domain(page_url, abs_href):
                self._add_unique(related_urls, abs_href)

            if self._is_contact_url(abs_href) or href.startswith("tel:") or href.startswith("mailto:"):
                self._add_unique(contact_urls, abs_href)

        return related_urls, contact_urls

    def extract_page_links(self, soup, page_url):
        related_urls = []
        contact_urls = []

        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            abs_href = self._abs_url(page_url, href)

            if not abs_href:
                continue

            if href.startswith("#"):
                continue

            if abs_href == page_url:
                continue

            if self._same_domain(page_url, abs_href):
                self._add_unique(related_urls, abs_href)

            if self._is_contact_url(abs_href) or href.startswith("tel:") or href.startswith("mailto:"):
                self._add_unique(contact_urls, abs_href)

        return related_urls, contact_urls

    def extract_images_from_block(self, block, page_url):
        images = []

        if not block:
            return images

        node = block.get("node")
        if not node:
            return images

        for img in node.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not src:
                continue

            src = self._abs_url(page_url, src)
            if self._is_probably_logo(src):
                continue

            self._add_unique(images, src)

        return images

    # --------------------------------------------------
    # structured entity extraction
    # --------------------------------------------------
    def extract_entity_jsonld_properties(self, item, page_url):
        props = {}
        related_urls = []
        contact_urls = []
        images = []

        if not isinstance(item, dict):
            return props

        if item.get("name"):
            props["name"] = self._clean_text(str(item["name"]))

        if item.get("description"):
            props["description"] = self.clean_description_text(str(item["description"]))

        if item.get("url"):
            props["url"] = self._abs_url(page_url, str(item["url"]))

        same_as = item.get("sameAs")
        if isinstance(same_as, list):
            for candidate in same_as:
                if isinstance(candidate, str):
                    self._add_unique(related_urls, candidate)
        elif isinstance(same_as, str):
            self._add_unique(related_urls, same_as)

        if item.get("telephone"):
            props["telephone"] = self._clean_phone(str(item["telephone"]))

        address = self._extract_postal_address(item.get("address"))
        if address:
            props["address"] = address

        geo = item.get("geo")
        if isinstance(geo, dict):
            if geo.get("latitude") is not None:
                props["latitude"] = str(geo.get("latitude"))
            if geo.get("longitude") is not None:
                props["longitude"] = str(geo.get("longitude"))

        if item.get("openingHours"):
            props["openingHours"] = item.get("openingHours")

        for image in self._extract_image_values(item.get("image"), page_url):
            self._add_unique(images, image)

        if item.get("@id") and isinstance(item["@id"], str) and item["@id"].startswith("http"):
            self._add_unique(related_urls, item["@id"])

        if related_urls:
            props["relatedUrls"] = related_urls

        if contact_urls:
            props["contactUrls"] = contact_urls

        if images:
            images = self._dedupe_images(images)
            if images:
                props["image"] = images[0]
                props["mainImage"] = images[0]
                if len(images) > 1:
                    props["additionalImages"] = images[1:]

        return props

    # --------------------------------------------------
    # main extraction
    # --------------------------------------------------
    def extract(self, html, text, url, entity):
        soup = BeautifulSoup(html, "html.parser")
        properties = {}

        # 1) JSON-LD específico de entidad
        jsonld_data = self.extract_jsonld(soup)
        for item in jsonld_data:
            if not isinstance(item, dict):
                continue

            name = item.get("name")
            if name and self._matches_entity(entity, str(name)):
                jsonld_props = self.extract_entity_jsonld_properties(item, url)
                properties.update(jsonld_props)

        # 2) bloque HTML más probable
        best_block = self.find_best_block_for_entity(soup, entity, page_url=url)
        if best_block:
            heading = best_block.get("heading", "")
            block_text = best_block.get("text", "")

            if heading and "name" not in properties:
                properties["name"] = heading

            if block_text and "description" not in properties:
                desc = block_text
                if heading and desc.startswith(heading):
                    desc = desc[len(heading):].strip()
                desc = self.clean_description_text(desc)
                if len(desc) > 50:
                    properties["description"] = desc[:700]

            if "telephone" not in properties:
                phone = self.extract_phone(block_text)
                if not phone:
                    node = best_block.get("node")
                    if node:
                        for a in node.find_all("a", href=True):
                            href = a.get("href", "")
                            if href.startswith("tel:"):
                                phone = self._clean_phone(href)
                                if phone:
                                    break
                if phone:
                    properties["telephone"] = phone

            if "address" not in properties:
                address = self.extract_address_from_text(block_text)
                if address:
                    properties["address"] = address

            geo = self.extract_geo(block_text)
            if "latitude" not in properties and geo.get("latitude"):
                properties["latitude"] = geo["latitude"]
            if "longitude" not in properties and geo.get("longitude"):
                properties["longitude"] = geo["longitude"]

            block_related, block_contact = self.extract_links_from_node(best_block.get("node"), url)
            if block_related:
                properties["relatedUrls"] = block_related
            if block_contact:
                properties["contactUrls"] = block_contact

            block_images = self.extract_images_from_block(best_block, url)
            if block_images and "image" not in properties:
                 # solo si el bloque menciona claramente la entidad
                block_images = self._dedupe_images(block_images)
                if block_images:
                    properties["image"] = block_images[0]
                    properties["mainImage"] = block_images[0]
                    if len(block_images) > 1:
                        properties["additionalImages"] = block_images[1:]

        # 3) meta fallback (SIN imagen global)
            meta_props = self.extract_meta(soup, page_url=url)

            for k, v in meta_props.items():
                if k in ("image", "mainImage"):
                    continue  # ❌ NO usar imagen global

                if k not in properties and v:
                    properties[k] = v

        # 4) fallback de página
        page_related, page_contact = self.extract_page_links(soup, url)
        if "relatedUrls" not in properties and page_related:
            properties["relatedUrls"] = page_related[:15]
        if "contactUrls" not in properties and page_contact:
            properties["contactUrls"] = page_contact[:10]

        geo = self.extract_geo(text)
        if geo.get("latitude") and "latitude" not in properties:
            properties["latitude"] = geo["latitude"]
        if geo.get("longitude") and "longitude" not in properties:
            properties["longitude"] = geo["longitude"]

        if "telephone" not in properties:
            phone = self.extract_phone(text)
            if phone:
                properties["telephone"] = phone

        if "address" not in properties:
            address = self.extract_address_from_text(text)
            if address:
                properties["address"] = address

        # 5) url principal siempre
        properties["url"] = properties.get("url") or url

        # 6) consistencia y deduplicación fuerte de imágenes
        all_images = []

        if properties.get("mainImage"):
            all_images.append(properties["mainImage"])

        if properties.get("image"):
            all_images.append(properties["image"])

        additional = properties.get("additionalImages")
        if isinstance(additional, list):
            all_images.extend(additional)
        elif additional:
            all_images.append(additional)

        deduped_images = self._dedupe_images(all_images)

        if deduped_images:
            properties["mainImage"] = deduped_images[0]
            properties["image"] = deduped_images[0]

            if len(deduped_images) > 1:
                properties["additionalImages"] = deduped_images[1:]
            else:
                properties.pop("additionalImages", None)
        else:
            properties.pop("mainImage", None)
            properties.pop("image", None)
            properties.pop("additionalImages", None)

        # 7) serialización limpia
        serialized = {}
        for key, value in properties.items():
            if value is None or value == "":
                continue

            if isinstance(value, list):
                clean_values = []
                for item in value:
                    if item and item not in clean_values:
                        clean_values.append(item)
                if clean_values:
                    serialized[key] = clean_values
            else:
                serialized[key] = value

        return serialized