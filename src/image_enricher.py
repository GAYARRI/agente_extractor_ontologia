import re
from urllib.parse import urljoin


class ImageEnricher:
    def __init__(self):
        self.max_images = 3
        self.generic_entity_tokens = {
            "burgos", "museo", "municipal", "catedral", "iglesia", "palacio",
            "monasterio", "convento", "santa", "maria", "real", "casa",
            "parque", "puente", "hotel", "ruta", "rutas", "camino",
        }

    # =========================================================
    # Helpers
    # =========================================================

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _tokens(self, text: str):
        text = self._normalize(text)
        return [t for t in re.split(r"[\s\-_/,.;:()]+", text) if len(t) > 3]

    def _entity_tokens(self, text: str):
        return [token for token in self._tokens(text) if token not in self.generic_entity_tokens]

    def _is_probably_image_url(self, url: str) -> bool:
        if not url:
            return False
        u = url.lower()
        return any(ext in u for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"])

    def _is_probably_logo(self, url: str) -> bool:
        return bool(self._image_rejection_reason(url))

    def _image_rejection_reason(self, url: str) -> str:
        if not url:
            return "missing_src"

        u = url.lower()

        if ".svg" in u:
            return "svg_or_vector_asset"

        bad_patterns = {
            "logo": "logo_or_brand_asset",
            "icon": "icon_asset",
            "iconos": "icon_asset",
            "sprite": "sprite_asset",
            "banner": "layout_asset",
            "menu-navegacion": "navigation_asset",
            "placeholder": "placeholder_asset",
            "default": "default_asset",
            "avatar": "avatar_asset",
            "header": "layout_asset",
            "footer": "layout_asset",
            "og-image": "generic_open_graph_asset",
            "share": "social_or_share_asset",
            "social": "social_or_share_asset",
            "twitter": "social_or_share_asset",
            "twitter+x": "social_or_share_asset",
            "twitter%2bx": "social_or_share_asset",
            "/x+1.": "social_or_share_asset",
            "/x_1.": "social_or_share_asset",
            "facebook": "social_or_share_asset",
            "instagram": "social_or_share_asset",
            "youtube": "social_or_share_asset",
            "separador": "decorative_asset",
            "separator": "decorative_asset",
            "feeling": "decorative_asset",
            "negativo": "decorative_asset",
            "_next/static/": "static_bundle_asset",
            "_next/image?": "proxy_or_transformed_asset",
            "/static/media/": "static_bundle_asset",
            "financion": "sponsor_asset",
            "fav": "favicon_asset",
            "favicon": "favicon_asset",
            "visita_burgos_fondo": "generic_background_asset",
            "burgos_fondo": "generic_background_asset",
            "_fondo": "generic_background_asset",
            "fondo.png": "generic_background_asset",
            "desliza.png": "generic_slider_placeholder",
        }

        for pattern, reason in bad_patterns.items():
            if pattern in u:
                return reason

        return ""

    def _extract_img_tags(self, html: str):
        if not html:
            return []

        pattern = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
        return pattern.findall(html)

    def _extract_attr(self, tag: str, attr: str) -> str:
        if not tag:
            return ""

        patterns = [
            rf'{attr}\s*=\s*"([^"]+)"',
            rf"{attr}\s*=\s*'([^']+)'",
        ]
        for pattern in patterns:
            match = re.search(pattern, tag, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def _get_img_src(self, tag: str, base_url: str = "") -> str:
        src = (
            self._extract_attr(tag, "src")
            or self._extract_attr(tag, "data-src")
            or self._extract_attr(tag, "data-lazy-src")
        )

        if not src:
            srcset = self._extract_attr(tag, "srcset")
            if srcset:
                src = srcset.split(",")[0].split(" ")[0].strip()

        if src and base_url:
            src = urljoin(base_url, src)

        return src

    def _image_relevance_score(
        self,
        entity: str,
        src: str,
        alt: str = "",
        title: str = "",
        text: str = "",
    ) -> int:
        score = 0

        entity_tokens = self._entity_tokens(entity)
        src_l = self._normalize(src)
        alt_l = self._normalize(alt)
        title_l = self._normalize(title)
        text_l = self._normalize(text)

        if self._is_probably_logo(src):
            score -= 10

        if any(x in src_l for x in ["logo", "icon", "iconos", "sprite", "banner", "placeholder"]):
            score -= 5

        if any(x in src_l for x in ["_next/static/", "_next/image?", "/static/media/", "financion"]):
            score -= 6

        if any(token in alt_l for token in entity_tokens):
            score += 6

        if any(token in title_l for token in entity_tokens):
            score += 5

        if any(token in src_l for token in entity_tokens):
            score += 3

        if (alt_l or title_l or any(token in src_l for token in entity_tokens)) and entity_tokens and any(token in text_l for token in entity_tokens):
            score += 1

        if alt_l:
            score += 1

        if title_l:
            score += 1

        if src_l.endswith((".jpg", ".jpeg", ".webp", ".png", ".avif")):
            score += 2

        if any(x in src_l for x in ["/sites/default/files/", "/migration/", "/images/"]):
            score += 2

        if any(x in src_l for x in ["home", "portada", "hero", "cabecera", "header", "cover"]):
            score -= 3

        if any(x in src_l for x in ["thumbnail", "thumb", "menu", "nav", "mapa"]):
            score -= 3

        if len(src_l) < 15:
            score -= 2

        return score

    def _context_relevance_score(
        self,
        src: str,
        alt: str = "",
        title: str = "",
        text: str = "",
    ) -> int:
        score = 0

        src_l = self._normalize(src)
        alt_l = self._normalize(alt)
        title_l = self._normalize(title)
        text_l = self._normalize(text)

        if self._is_probably_logo(src):
            score -= 10

        if alt_l:
            score += 2

        if title_l:
            score += 1

        if src_l.endswith((".jpg", ".jpeg", ".webp", ".png", ".avif")):
            score += 2

        if any(x in src_l for x in ["/sites/default/files/", "/migration/", "/images/"]):
            score += 2

        if any(x in src_l for x in ["hero", "cover", "cabecera", "header", "portada", "featured", "gallery", "slide"]):
            score += 2

        if any(x in alt_l for x in ["foto", "imagen", "vista", "fachada", "interior"]):
            score += 1

        if any(x in src_l for x in ["thumbnail", "thumb", "menu", "nav", "mapa"]):
            score -= 2

        alt_tokens = self._tokens(alt_l or title_l)
        if text_l and alt_tokens and any(token in text_l for token in alt_tokens):
            score += 1

        if len(src_l) < 15:
            score -= 2

        return score

    def _extract_text_image_urls(self, text: str):
        if not text:
            return []

        urls = re.findall(r'https?://[^\s<>"\']+', text)
        return [url for url in urls if self._is_probably_image_url(url)]

    def _extract_meta_image_urls(self, html: str, base_url: str = ""):
        if not html:
            return []
        urls = []
        meta_pattern = re.compile(
            r"<meta\b[^>]*(?:property|name)\s*=\s*['\"](?:og:image|twitter:image|twitter:image:src)['\"][^>]*>",
            re.IGNORECASE,
        )
        for tag in meta_pattern.findall(html):
            src = self._extract_attr(tag, "content")
            if src and base_url:
                src = urljoin(base_url, src)
            if src and self._is_probably_image_url(src):
                urls.append(src)

        json_image_pattern = re.compile(r'"image"\s*:\s*"([^"]+)"', re.IGNORECASE)
        for src in json_image_pattern.findall(html):
            if src and base_url:
                src = urljoin(base_url, src)
            if src and self._is_probably_image_url(src):
                urls.append(src)
        return urls

    def _record(
        self,
        src: str,
        entity_score: int,
        context_score: int,
        source: str,
        alt: str = "",
        title: str = "",
    ):
        reason = self._image_rejection_reason(src)
        accepted = (
            not reason
            and entity_score + context_score >= 6
            and entity_score >= 4
        )
        if not reason and not accepted:
            reason = "weak_image_affinity"
        return {
            "src": src,
            "source": source,
            "alt": alt,
            "title": title,
            "entity_score": entity_score,
            "context_score": context_score,
            "combined_score": entity_score + context_score,
            "accepted": accepted,
            "rejectionReason": reason,
        }

    def _collect_candidate_records(self, entity: str, text: str = "", html: str = "", url: str = ""):
        records = []

        for img in self._extract_text_image_urls(text):
            entity_score = self._image_relevance_score(entity, img, text=text) + 2
            context_score = self._context_relevance_score(img, text=text) + 1
            records.append(self._record(img, entity_score, context_score, source="text_url"))

        for img in self._extract_meta_image_urls(html, base_url=url):
            entity_score = self._image_relevance_score(entity, img, text=text)
            context_score = self._context_relevance_score(img, text=text) + 1
            records.append(self._record(img, entity_score, context_score, source="meta_or_jsonld"))

        for tag in self._extract_img_tags(html):
            src = self._get_img_src(tag, base_url=url)
            if not src or not self._is_probably_image_url(src):
                continue

            alt = self._extract_attr(tag, "alt")
            title = self._extract_attr(tag, "title")
            entity_score = self._image_relevance_score(entity, src, alt=alt, title=title, text=text)
            context_score = self._context_relevance_score(src, alt=alt, title=title, text=text)
            records.append(self._record(src, entity_score, context_score, source="img_tag", alt=alt, title=title))

        best_by_src = {}
        for record in records:
            src = record["src"]
            if src not in best_by_src or record["combined_score"] > best_by_src[src]["combined_score"]:
                best_by_src[src] = record

        return sorted(
            best_by_src.values(),
            key=lambda item: (item["combined_score"], item["entity_score"], item["context_score"]),
            reverse=True,
        )

    def _is_entity_representative(self, record) -> bool:
        return (
            record["entity_score"] >= 4
            and record["combined_score"] >= 5
        )

    def _is_context_representative(self, record) -> bool:
        return (
            record["context_score"] >= 3
            and record["combined_score"] >= 5
        )

    def _choose_distinct_images(self, records):
        if not records:
            return "", "", []

        relevant = [
            record for record in records
            if record.get("accepted")
            if record["combined_score"] >= 5
            and (record["entity_score"] >= 3 or record["context_score"] >= 3)
        ]
        if not relevant:
            return "", "", []

        entity_ranked = sorted(
            [record for record in relevant if self._is_entity_representative(record)] or relevant,
            key=lambda item: (item["entity_score"], item["combined_score"], item["context_score"]),
            reverse=True,
        )
        context_ranked = sorted(
            [record for record in relevant if self._is_context_representative(record)] or relevant,
            key=lambda item: (item["context_score"], item["combined_score"], item["entity_score"]),
            reverse=True,
        )

        primary_record = entity_ranked[0] if entity_ranked else relevant[0]
        image = primary_record["src"] if primary_record else ""
        main_image = image
        context_threshold = min(max(primary_record["combined_score"] - 3, 5), 9)
        support_threshold = min(max(primary_record["combined_score"] - 2, 5), 10)

        for item in context_ranked:
            if item["src"] == image:
                continue
            if (
                self._is_context_representative(item)
                and item["combined_score"] >= context_threshold
            ):
                main_image = item["src"]
                break

        ordered = []
        seen = set()

        for src in [image, main_image]:
            if src and src not in seen:
                seen.add(src)
                ordered.append(src)

        for item in relevant:
            if len(ordered) >= self.max_images:
                break

            src = item["src"]
            if src and src not in seen:
                if item["combined_score"] < support_threshold:
                    continue
                if item["entity_score"] < 4 and item["context_score"] < 4:
                    continue
                seen.add(src)
                ordered.append(src)

        return image, main_image or image, ordered

    # =========================================================
    # API publica
    # =========================================================

    def enrich(self, entity, text="", html="", url=""):
        records = self._collect_candidate_records(entity=entity, text=text, html=html, url=url)

        if not records:
            return {}

        image, main_image, ordered_images = self._choose_distinct_images(records)
        best = ordered_images[0] if ordered_images else ""
        best_record = next((item for item in records if item["src"] == best), None)
        score = best_record["combined_score"] if best_record else 0
        accepted_records = [record for record in records if record.get("accepted")]
        rejected_records = [record for record in records if not record.get("accepted")]
        candidate_images = [record["src"] for record in accepted_records[: self.max_images * 3]]
        rejected_images = [
            {
                "src": record["src"],
                "reason": record.get("rejectionReason") or "weak_or_invalid_candidate",
                "source": record.get("source", ""),
                "score": record.get("combined_score", 0),
            }
            for record in rejected_records[:10]
        ]
        image_evidence = [
            {
                "src": record["src"],
                "source": record.get("source", ""),
                "score": record.get("combined_score", 0),
                "entityScore": record.get("entity_score", 0),
                "contextScore": record.get("context_score", 0),
                "accepted": bool(record.get("accepted")),
                "rejectionReason": record.get("rejectionReason", ""),
            }
            for record in records[:12]
        ]

        if score >= 5:
            return {
                "image": image,
                "mainImage": main_image,
                "images": ordered_images,
                "additionalImages": ordered_images[1:] if len(ordered_images) > 1 else [],
                "candidateImages": candidate_images,
                "rejectedImages": rejected_images,
                "imageEvidence": image_evidence,
                "debug": {
                    "image_score": score,
                    "image_reason": "ranked_entity_and_context_candidates",
                    "image_entity_score": best_record["entity_score"] if best_record else 0,
                    "image_context_score": best_record["context_score"] if best_record else 0,
                },
            }

        if accepted_records:
            return {
                "candidateImage": accepted_records[0]["src"],
                "candidateImages": candidate_images,
                "rejectedImages": rejected_images,
                "imageEvidence": image_evidence,
                "debug": {
                    "image_score": accepted_records[0].get("combined_score", 0),
                    "image_reason": "weak_candidate_from_html_or_text",
                },
            }

        return {
            "rejectedImages": rejected_images,
            "imageEvidence": image_evidence,
        }
