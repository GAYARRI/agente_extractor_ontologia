# src/dom_image_resolver.py

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class DOMImageResolver:
    def __init__(self):
        pass

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _tokens(self, text: str):
        text = self._normalize(text)
        return [t for t in re.split(r"[\s\-_/,.;:()]+", text) if len(t) > 3]

    def _is_bad_image(self, src: str) -> bool:
        if not src:
            return True

        s = src.lower()
        bad = [
            "logo", "icon", "sprite", "banner", "placeholder",
            "header", "footer", "avatar", "share", "social",
            "default", "site-logo", "separador", "separator"
        ]
        return any(b in s for b in bad)

    def _get_img_src(self, img, base_url="") -> str:
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
            or ""
        ).strip()

        if not src:
            srcset = (img.get("srcset") or "").strip()
            if srcset:
                src = srcset.split(",")[0].split(" ")[0].strip()

        if src and base_url:
            src = urljoin(base_url, src)

        return src

    def _score_image(self, entity_name: str, img, src: str, zone_weight: int = 0) -> int:
        score = zone_weight
        entity_tokens = self._tokens(entity_name)

        alt = self._normalize(img.get("alt", ""))
        title = self._normalize(img.get("title", ""))
        cls = self._normalize(" ".join(img.get("class", [])) if img.get("class") else "")
        src_l = self._normalize(src)

        if self._is_bad_image(src):
            score -= 10

        if any(t in alt for t in entity_tokens):
            score += 5

        if any(t in title for t in entity_tokens):
            score += 4

        if any(t in src_l for t in entity_tokens):
            score += 3

        if "wp-image" in cls:
            score += 1

        if src_l.endswith(".jpg") or src_l.endswith(".jpeg") or src_l.endswith(".webp"):
            score += 1

        width = img.get("width")
        height = img.get("height")
        try:
            if width and height and int(width) >= 200 and int(height) >= 200:
                score += 1
        except Exception:
            pass

        return score

    def _images_from_zone(self, zone, entity_name: str, base_url: str = "", zone_weight: int = 0):
        if zone is None:
            return []

        out = []
        for img in zone.find_all("img"):
            src = self._get_img_src(img, base_url=base_url)
            if not src:
                continue
            score = self._score_image(entity_name, img, src, zone_weight=zone_weight)
            out.append((src, score))
        return out

    def _best(self, candidates):
        if not candidates:
            return "", 0

        best_by_src = {}
        for src, score in candidates:
            if src not in best_by_src or score > best_by_src[src]:
                best_by_src[src] = score

        ordered = sorted(best_by_src.items(), key=lambda x: x[1], reverse=True)
        return ordered[0]

    def _find_nodes_matching_text(self, soup, block_text: str, entity_name: str):
        block_norm = self._normalize(block_text)
        entity_norm = self._normalize(entity_name)

        matches = []

        for node in soup.find_all(["p", "div", "section", "article", "li", "span", "h1", "h2", "h3", "h4"]):
            txt = self._normalize(node.get_text(" ", strip=True))
            if not txt:
                continue

            if entity_norm and entity_norm in txt:
                matches.append(node)
                continue

            if block_norm and len(block_norm) > 40 and block_norm[:80] in txt:
                matches.append(node)

        return matches

    def resolve_with_score(self, html: str, entity_name: str, base_url: str = "", block_text: str = "", min_score: int = 0):
        if not html or not entity_name:
            return "", 0

        soup = BeautifulSoup(html, "html.parser")
        candidates = []

        matched_nodes = self._find_nodes_matching_text(soup, block_text, entity_name)

        # 1. Bloque local exacto
        for node in matched_nodes:
            candidates.extend(self._images_from_zone(node, entity_name, base_url=base_url, zone_weight=6))

            parent = node.parent
            if parent:
                candidates.extend(self._images_from_zone(parent, entity_name, base_url=base_url, zone_weight=4))

            grandparent = parent.parent if parent and parent.parent else None
            if grandparent:
                candidates.extend(self._images_from_zone(grandparent, entity_name, base_url=base_url, zone_weight=2))

        # 2. Fallback global muy débil
        if not candidates:
            for img in soup.find_all("img"):
                src = self._get_img_src(img, base_url=base_url)
                if not src:
                    continue
                score = self._score_image(entity_name, img, src, zone_weight=0)
                candidates.append((src, score))

        src, score = self._best(candidates)

        if src and score >= min_score:
            return src, score

        return "", 0

    def resolve(self, html: str, entity_name: str, base_url: str = "", block_text: str = "", min_score: int = 4) -> str:
        src, score = self.resolve_with_score(
            html=html,
            entity_name=entity_name,
            base_url=base_url,
            block_text=block_text,
            min_score=min_score
        )
        return src if score >= min_score else ""

    def resolve_image_for_entity(self, html: str, entity_name: str) -> str:
        src, score = self.resolve_with_score(html, entity_name, min_score=3)
        return src if score >= 3 else ""
