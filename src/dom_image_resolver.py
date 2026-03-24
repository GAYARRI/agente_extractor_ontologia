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
            "default", "site-logo"
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

    def _score_image(self, entity_name: str, img, src: str) -> int:
        score = 0
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

    def _find_best_near_text(self, soup, entity_name: str, base_url=""):
        target = self._normalize(entity_name)
        if not target:
            return "", 0

        candidates = []

        for text_node in soup.find_all(string=True):
            txt = self._normalize(str(text_node))
            if not txt or target not in txt:
                continue

            node = text_node.parent
            if node is None:
                continue

            zones = [
                node,
                node.parent,
                node.parent.parent if node.parent and node.parent.parent else None,
            ]

            for zone in zones:
                if zone is None:
                    continue
                for img in zone.find_all("img"):
                    src = self._get_img_src(img, base_url=base_url)
                    if not src:
                        continue
                    score = self._score_image(entity_name, img, src)
                    candidates.append((src, score))

        if not candidates:
            return "", 0

        best = sorted(candidates, key=lambda x: x[1], reverse=True)[0]
        return best

    def resolve(self, html: str, entity_name: str, base_url: str = "", min_score: int = 4) -> str:
        src, score = self.resolve_with_score(html, entity_name, base_url=base_url, min_score=min_score)
        return src if score >= min_score else ""    
        
    
    def resolve_with_score(self, html: str, entity_name: str, base_url: str = "", min_score: int = 0):
        if not html or not entity_name:
            return "", 0

        soup = BeautifulSoup(html, "html.parser")
        src, score = self._find_best_near_text(soup, entity_name, base_url=base_url)

        if src and score >= min_score:
            return src, score

        return "", 0
