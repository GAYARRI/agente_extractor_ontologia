import json
import re
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
                "latitude",
                "longitude",
                "openingHours",
                "image",
            ]

        self.properties = properties

    # --------------------------------------------------
    # helpers
    # --------------------------------------------------

    def _normalize(self, text: str) -> str:
        return " ".join(text.strip().lower().split())

    def _matches_entity(self, entity: str, candidate: str) -> bool:
        if not entity or not candidate:
            return False

        e = self._normalize(entity)
        c = self._normalize(candidate)

        return e == c or e in c or c in e

    def _clean_text(self, text: str) -> str:
        return " ".join(text.strip().split())

    # --------------------------------------------------
    # block extraction
    # --------------------------------------------------

    def extract_blocks(self, soup):
        blocks = []

        candidates = soup.find_all(["section", "article", "div", "li"])

        for node in candidates:
            text = self._clean_text(node.get_text(" ", strip=True))

            if len(text) < 60:
                continue

            heading_tag = node.find(["h1", "h2", "h3", "h4"])
            heading = self._clean_text(heading_tag.get_text(" ", strip=True)) if heading_tag else ""

            img = node.find("img")
            image = img.get("src") if img and img.get("src") else None

            blocks.append({
                "heading": heading,
                "text": text,
                "image": image,
                "node": node,
            })

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

        # penalizar bloques claramente colectivos
        collective_patterns = [
            "desde ",
            "hasta ",
            "entre ",
            "como ",
            "rincones ",
            "playas vírgenes",
            "playas naturales",
        ]

        if any(p in text_n for p in collective_patterns):
            score -= 0.3

        return score

    def find_best_block_for_entity(self, soup, entity):
        blocks = self.extract_blocks(soup)

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

    def extract_meta(self, soup):
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
                props["image"] = content.strip()

            elif prop == "twitter:image" and "image" not in props:
                props["image"] = content.strip()

        return props

    # --------------------------------------------------
    # block-level extraction
    # --------------------------------------------------

    def extract_block_description(self, block):
        if not block:
            return None

        text = block.get("text", "")
        heading = block.get("heading", "")

        if heading and text.startswith(heading):
            text = text[len(heading):].strip()

        if len(text) > 500:
            text = text[:500].rsplit(" ", 1)[0]

        return text if len(text) > 50 else None

    def extract_block_image(self, block):
        if not block:
            return None

        image = block.get("image")
        if not image:
            return None

        image_l = image.lower()
        if "logo" in image_l:
            return None

        return image

    # --------------------------------------------------
    # fallback extraction
    # --------------------------------------------------

    def extract_geo(self, text):
        geo = {}

        latlon = re.search(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", text)

        if latlon:
            geo["latitude"] = latlon.group(1)
            geo["longitude"] = latlon.group(2)

        return geo

    
    def extract_phone(self, text):
        if not text:
            return None

        matches = re.findall(r"(?:\+34\s*)?(?:\(?\d{2,3}\)?[\s\-]*){3,5}", text)

        for match in matches:
            digits = re.sub(r"\D", "", match)

            # teléfono español razonable: 9 dígitos o 11 con prefijo 34
            if len(digits) == 9 or (len(digits) == 11 and digits.startswith("34")):
                return match.strip()

        return None    
    
    def clean_description_text(self, text: str) -> str:
        if not text:
            return ""

        # quitar imágenes markdown
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)

        # quitar enlaces markdown dejando el texto visible
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

        # quitar headings markdown
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

        noise_lines = [
            "watch later",
            "share",
            "copy link",
            "tap to unmute",
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

    
    def clean_description_text(self, text: str) -> str:
        if not text:
            return ""

        # quitar imágenes markdown
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)

        # quitar enlaces markdown, dejando solo el texto visible
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

        # quitar headings markdown
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

        # quitar líneas típicas de UI / vídeo
        noise_lines = [
            "watch later",
            "share",
            "copy link",
            "tap to unmute",
            "youtube",
            "subscribers",
            "ver video",
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
    # extracción por bloque
    # --------------------------------------------------

    def extract_from_block(self, block, entity, block_is_collective=False):
        properties = {}

        heading = block.get("heading", "")
        text = block.get("text", "")
        image = block.get("image")
        page_url = block.get("page_url", "")

        # nombre desde heading si coincide
        if heading and self._matches_entity(entity, heading):
            properties["name"] = heading

        # descripción solo si el bloque NO es colectivo
        
        if text:
            desc = text
            if heading and desc.startswith(heading):
                desc = desc[len(heading):].strip()

            if len(desc) > 500:
                desc = desc[:500].rsplit(" ", 1)[0]

            desc = self.clean_description_text(desc)

            if not block_is_collective and len(desc) > 50:
                properties["description"] = desc

        # imagen solo si el bloque NO es colectivo y no parece logo
        if image and "logo" not in image.lower() and not block_is_collective:
            properties["image"] = image

        # url de página
        if page_url:
            properties["url"] = page_url

        # teléfono si aparece dentro del bloque
        phone = self.extract_phone(text)
        if phone:
            properties["telephone"] = phone


        geo = self.extract_geo(text)
        for k, v in geo.items():
            properties[k] = v

        return properties
    




    # --------------------------------------------------
    # main page-level fallback
    # --------------------------------------------------

    def extract(self, html, text, url, entity):
        soup = BeautifulSoup(html, "html.parser")
        properties = {}

        # 1. JSON-LD específico de entidad
        jsonld_data = self.extract_jsonld(soup)

        for item in jsonld_data:
            if not isinstance(item, dict):
                continue

            name = item.get("name")

            if name and self._matches_entity(entity, name):
                for prop in self.properties:
                    if prop in item:
                        properties[prop] = item[prop]

                if "description" in item and "description" not in properties:
                    properties["description"] = item["description"]

                if "image" in item and "image" not in properties:
                    if isinstance(item["image"], str):
                        properties["image"] = item["image"]
                    elif isinstance(item["image"], list) and item["image"]:
                        properties["image"] = item["image"][0]

                geo = item.get("geo")
                if isinstance(geo, dict):
                    if "latitude" in geo:
                        properties["latitude"] = geo["latitude"]
                    if "longitude" in geo:
                        properties["longitude"] = geo["longitude"]

        # 2. bloque HTML más probable para la entidad
        best_block = self.find_best_block_for_entity(soup, entity)

        if best_block:
            block_desc = self.extract_block_description(best_block)
            if block_desc and "description" not in properties:
                properties["description"] = block_desc

            block_image = self.extract_block_image(best_block)
            if block_image and "image" not in properties:
                properties["image"] = block_image

            if best_block.get("heading") and "name" not in properties:
                properties["name"] = best_block["heading"]

        # 3. meta como fallback suave
        meta_props = self.extract_meta(soup)

        for k, v in meta_props.items():
            if k not in properties and v:
                properties[k] = v

        # 4. geolocalización fallback
        geo = self.extract_geo(text)
        for k, v in geo.items():
            if k not in properties:
                properties[k] = v

        # 5. teléfono fallback
        phone = self.extract_phone(text)
        if phone and "telephone" not in properties:
            properties["telephone"] = phone

        # 6. url siempre
        properties["url"] = url

        return properties