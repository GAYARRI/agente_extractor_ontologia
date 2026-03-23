from rdflib import Graph, Namespace, URIRef, Literal
import re
import html
import os
from urllib.parse import urlparse, urlunparse, unquote


class KnowledgeGraphBuilder:

    def __init__(self, ontology_index=None):

        self.graph = Graph()

        # Namespaces
        self.EX = Namespace("http://example.org/resource/")
        self.TOUR = Namespace("http://example.org/tourism/")

        self.graph.bind("ex", self.EX)
        self.graph.bind("tour", self.TOUR)

        self.ontology_index = ontology_index

    # ==================================================
    # HELPERS GENERALES
    # ==================================================

    def _safe_text(self, value):
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _normalize_text(self, text):
        return " ".join(self._safe_text(text).lower().split())

    def _entity_tokens(self, value):
        value = self._normalize_text(value)
        tokens = []

        for token in value.replace("-", " ").replace("/", " ").split():
            token = "".join(ch for ch in token if ch.isalnum() or ch in "áéíóúñü")
            if len(token) >= 3:
                tokens.append(token)

        return set(tokens)

    def _normalize_url(self, url):
        if not url:
            return None

        url = self._safe_text(url)
        if not url:
            return None

        if url.startswith(("mailto:", "tel:")):
            return url

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None

        return unquote(urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            "",
            "",
            ""
        )).rstrip("/"))

    def _image_signature(self, url):
        norm = self._normalize_url(url)
        if not norm:
            return None

        path = unquote(urlparse(norm).path).lower()
        filename = os.path.basename(path)
        return filename or path

    def _looks_generic_url(self, url):
        if not url or url.startswith(("mailto:", "tel:")):
            return False

        low = url.lower()
        return any(x in low for x in [
            "/contact",
            "/contacto",
            "/cookies",
            "/cookie",
            "/privacy",
            "/privacidad",
            "/legal",
            "/aviso-legal",
            "/mapa-web",
            "/sitemap",
            "/author/",
            "/tag/",
            "/feed",
            "/wp-json",
        ])

    def _url_score(self, entity_name, url):
        if not url or url.startswith(("mailto:", "tel:")):
            return 0

        entity_tokens = self._entity_tokens(entity_name)
        url_tokens = self._entity_tokens(unquote(urlparse(url).path))

        overlap = len(entity_tokens & url_tokens)
        return overlap * 3 + (2 if overlap > 0 else 0)

    def _is_probably_image(self, value):
        if not value:
            return False
        low = value.lower()
        return any(ext in low for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"])

    def _dedupe_list(self, values):
        result = []
        seen = set()

        for value in values or []:
            norm = self._safe_text(value)
            if not norm:
                continue
            if norm in seen:
                continue
            seen.add(norm)
            result.append(value)

        return result

    def _clean_entity_properties(self, entity_label, props):
        props = dict(props or {})

        # URL principal
        main_url = self._normalize_url(props.get("url"))
        if main_url and self._url_score(entity_label, main_url) >= 2 and not self._looks_generic_url(main_url):
            props["url"] = main_url
        else:
            props.pop("url", None)

        # sourceUrl: la dejamos, pero solo si es válida
        source_url = self._normalize_url(props.get("sourceUrl"))
        if source_url:
            props["sourceUrl"] = source_url
        else:
            props.pop("sourceUrl", None)

        # relatedUrls / contactUrls
        for key in ("relatedUrls", "contactUrls"):
            values = props.get(key, [])
            if not isinstance(values, list):
                values = [values] if values else []

            cleaned = []
            seen = set()

            for value in values:
                norm = self._normalize_url(value) if not str(value).startswith(("mailto:", "tel:")) else self._safe_text(value)
                if not norm:
                    continue
                if norm in seen:
                    continue

                if key == "relatedUrls":
                    if norm.startswith(("http://", "https://")):
                        if self._looks_generic_url(norm):
                            continue
                        if self._url_score(entity_label, norm) < 2:
                            continue
                        if props.get("url") and norm == props["url"]:
                            continue

                cleaned.append(norm)
                seen.add(norm)

            if cleaned:
                props[key] = cleaned[:10]
            else:
                props.pop(key, None)

        # imágenes
        images = []

        for key in ("mainImage", "image"):
            value = self._normalize_url(props.get(key))
            if value and self._is_probably_image(value):
                images.append(value)

        additional = props.get("additionalImages", [])
        if not isinstance(additional, list):
            additional = [additional] if additional else []

        for value in additional:
            norm = self._normalize_url(value)
            if norm and self._is_probably_image(norm):
                images.append(norm)

        # dedupe por firma de archivo
        deduped = []
        seen_sigs = set()

        for img in images:
            sig = self._image_signature(img)
            if not sig or sig in seen_sigs:
                continue
            seen_sigs.add(sig)
            deduped.append(img)

        if deduped:
            props["mainImage"] = deduped[0]
            props["image"] = deduped[0]
            if len(deduped) > 1:
                props["additionalImages"] = deduped[1:4]
            else:
                props.pop("additionalImages", None)
        else:
            props.pop("mainImage", None)
            props.pop("image", None)
            props.pop("additionalImages", None)

        return props

    # ==================================================
    # NORMALIZACIÓN DE ENTIDADES
    # ==================================================

    def normalize_entity(self, label):

        if not label:
            return ""

        label = self._normalize_text(label)

        # quitar caracteres raros
        label = re.sub(r"[^\w\s-]", "", label)

        # espacios y guiones → _
        label = re.sub(r"[\s\-]+", "_", label)

        return label.strip("_")

    # ==================================================
    # NORMALIZACIÓN DE PROPIEDADES
    # ==================================================

    def normalize_property(self, label):
        if not label:
            return ""

        label = str(label).strip()
        label = re.sub(r"[^\w\s]", "", label)
        label = re.sub(r"\s+", "_", label)

        if not label:
            return ""

        if label[0].isdigit():
            label = f"p_{label}"

        return label

    # ==================================================
    # BUILD DEL GRAFO
    # ==================================================

    def build(self, results):
        # reset para evitar acumulaciones si se llama varias veces
        self.graph = Graph()
        self.graph.bind("ex", self.EX)
        self.graph.bind("tour", self.TOUR)

        entity_map = {}

        for block in results:
            entities = block.get("entities", [])

            for entity in entities:
                label = entity.get("entity") or entity.get("entity_name")

                if not label:
                    continue

                normalized = self.normalize_entity(label)

                if not normalized:
                    continue

                key = normalized

                if key not in entity_map:
                    entity_map[key] = {
                        "label": label,
                        "class": entity.get("class", "Place"),
                        "score": entity.get("score"),
                        "sourceUrl": block.get("url"),
                        "properties": {},
                        "short_description": entity.get("short_description"),
                        "long_description": entity.get("long_description"),
                        "wikidata_id": entity.get("wikidata_id"),
                    }

                # score máximo
                current_score = entity_map[key].get("score")
                new_score = entity.get("score")
                if new_score is not None and (current_score is None or new_score > current_score):
                    entity_map[key]["score"] = new_score

                # clase
                if entity.get("class"):
                    entity_map[key]["class"] = entity.get("class")

                # sourceUrl
                if not entity_map[key].get("sourceUrl") and block.get("url"):
                    entity_map[key]["sourceUrl"] = block.get("url")

                # descripciones
                if entity.get("short_description") and (
                    not entity_map[key].get("short_description")
                    or len(entity.get("short_description", "")) > len(entity_map[key].get("short_description", ""))
                ):
                    entity_map[key]["short_description"] = entity.get("short_description")

                if entity.get("long_description") and (
                    not entity_map[key].get("long_description")
                    or len(entity.get("long_description", "")) > len(entity_map[key].get("long_description", ""))
                ):
                    entity_map[key]["long_description"] = entity.get("long_description")

                # wikidata
                if not entity_map[key].get("wikidata_id") and entity.get("wikidata_id"):
                    entity_map[key]["wikidata_id"] = entity.get("wikidata_id")

                # merge props
                props = entity.get("properties", {}) or {}
                current_props = entity_map[key]["properties"]

                for k, v in props.items():
                    if not k or v is None or v == "":
                        continue

                    if k not in current_props:
                        current_props[k] = v
                        continue

                    old = current_props[k]

                    if isinstance(old, list):
                        old_list = old
                    else:
                        old_list = [old]

                    incoming = v if isinstance(v, list) else [v]
                    merged = self._dedupe_list(old_list + incoming)
                    current_props[k] = merged if len(merged) > 1 else merged[0]

        # construir grafo con limpieza final
        for key, item in entity_map.items():
            subject = URIRef(self.EX[key])

            label = item.get("label") or key
            clean_props = self._clean_entity_properties(label, item.get("properties", {}))

            # incorporar sourceUrl si no vino dentro de props
            if item.get("sourceUrl") and "sourceUrl" not in clean_props:
                source_url = self._normalize_url(item.get("sourceUrl"))
                if source_url:
                    clean_props["sourceUrl"] = source_url

            self.graph.add((
                subject,
                self.TOUR.label,
                Literal(label)
            ))

            entity_class = item.get("class", "Place")
            self.graph.add((
                subject,
                self.TOUR.type,
                Literal(entity_class)
            ))

            score = item.get("score")
            if score is not None:
                self.graph.add((
                    subject,
                    self.TOUR.score,
                    Literal(score)
                ))

            for k, v in clean_props.items():
                if not k or v is None or v == "":
                    continue

                pred_name = self.normalize_property(k)
                if not pred_name:
                    continue

                pred = self.TOUR[pred_name]

                if isinstance(v, list):
                    for item_value in v:
                        if item_value is None or item_value == "":
                            continue
                        self.graph.add((
                            subject,
                            pred,
                            Literal(str(item_value))
                        ))
                else:
                    self.graph.add((
                        subject,
                        pred,
                        Literal(str(v))
                    ))

            short_desc = item.get("short_description")
            long_desc = item.get("long_description")

            if short_desc:
                self.graph.add((
                    subject,
                    self.TOUR.shortDescription,
                    Literal(short_desc)
                ))

            if long_desc:
                self.graph.add((
                    subject,
                    self.TOUR.longDescription,
                    Literal(long_desc)
                ))

            wikidata_id = item.get("wikidata_id")
            if wikidata_id:
                wikidata_url = f"https://www.wikidata.org/wiki/{wikidata_id}"
                self.graph.add((
                    subject,
                    self.TOUR.wikidata,
                    Literal(wikidata_url)
                ))

    # ==================================================
    # GUARDAR TTL
    # ==================================================

    def save(self, path):
        self.graph.serialize(destination=path, format="turtle")

    # ==================================================
    # EXPORTAR HTML SIMPLE
    # ==================================================

    def save_html(self, path):

        entities = {}

        for s, p, o in self.graph:
            s_str = str(s)
            p_str = str(p)
            o_str = str(o)

            entity_id = s_str.split("/")[-1]
            prop_name = p_str.split("/")[-1]

            if entity_id not in entities:
                entities[entity_id] = {}

            if prop_name not in entities[entity_id]:
                entities[entity_id][prop_name] = []

            if o_str not in entities[entity_id][prop_name]:
                entities[entity_id][prop_name].append(o_str)

        html_parts = []
        html_parts.append("""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Knowledge Graph</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 30px;
            background: #f7f7f7;
            color: #222;
        }
        h1 {
            margin-bottom: 10px;
        }
        .entity {
            background: white;
            border-radius: 10px;
            padding: 18px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .entity h2 {
            margin-top: 0;
            color: #0b5cab;
        }
        .prop {
            margin: 6px 0;
        }
        .prop strong {
            display: inline-block;
            min-width: 180px;
        }
        img {
            max-width: 320px;
            max-height: 220px;
            display: block;
            margin-top: 8px;
            border-radius: 8px;
        }
        a {
            color: #0b5cab;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .value-list {
            margin-left: 0;
            padding-left: 18px;
        }
    </style>
</head>
<body>
    <h1>Knowledge Graph</h1>
    <p>Total de entidades: """ + str(len(entities)) + """</p>
""")

        for entity_id, props in sorted(entities.items()):

            label = props.get("label", [entity_id])[0]
            label = html.escape(str(label))

            html_parts.append('<div class="entity">')
            html_parts.append(f"<h2>{label}</h2>")

            preferred_order = [
                "type",
                "score",
                "sourceUrl",
                "url",
                "relatedUrls",
                "contactUrls",
                "address",
                "telephone",
                "latitude",
                "longitude",
                "mainImage",
                "image",
                "additionalImages",
                "shortDescription",
                "longDescription",
                "wikidata"
            ]

            shown = set()

            for prop_name in preferred_order:
                if prop_name in props:
                    self._append_html_property(html_parts, prop_name, props[prop_name])
                    shown.add(prop_name)

            for prop_name, values in sorted(props.items()):
                if prop_name in shown or prop_name == "label":
                    continue
                self._append_html_property(html_parts, prop_name, values)

            html_parts.append("</div>")

        html_parts.append("""
</body>
</html>
""")

        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(html_parts))

    # ==================================================
    # HELPER HTML
    # ==================================================

    def _append_html_property(self, html_parts, prop_name, values):

        if not values:
            return

        if not isinstance(values, list):
            values = [values]

        image_props = {"image", "mainImage", "additionalImages"}
        url_like_props = {"url", "sourceUrl", "wikidata", "relatedUrls", "contactUrls"}

        clean_values = []
        seen = set()

        for value in values:
            text_value = self._safe_text(value)
            if not text_value:
                continue
            if text_value in seen:
                continue
            seen.add(text_value)
            clean_values.append(text_value)

        if not clean_values:
            return

        if prop_name in image_props:
            html_parts.append(f'<div class="prop"><strong>{html.escape(prop_name)}:</strong></div>')
            for value in clean_values:
                if not self._is_probably_image(value):
                    continue
                safe_value = html.escape(str(value))
                html_parts.append(f'<img src="{safe_value}" alt="{html.escape(prop_name)}">')
            return

        if len(clean_values) == 1:
            value = str(clean_values[0])

            if prop_name in url_like_props and (
                value.startswith("http://")
                or value.startswith("https://")
                or value.startswith("mailto:")
                or value.startswith("tel:")
            ):
                safe_href = html.escape(value)
                safe_text = html.escape(value)
                html_parts.append(
                    f'<div class="prop"><strong>{html.escape(prop_name)}:</strong> '
                    f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer">{safe_text}</a></div>'
                )
            else:
                safe_value = html.escape(value)
                html_parts.append(
                    f'<div class="prop"><strong>{html.escape(prop_name)}:</strong> {safe_value}</div>'
                )
            return

        html_parts.append(f'<div class="prop"><strong>{html.escape(prop_name)}:</strong></div>')
        html_parts.append('<ul class="value-list">')

        for value in clean_values:
            value = str(value)
            if prop_name in url_like_props and (
                value.startswith("http://")
                or value.startswith("https://")
                or value.startswith("mailto:")
                or value.startswith("tel:")
            ):
                safe_href = html.escape(value)
                safe_text = html.escape(value)
                html_parts.append(
                    f'<li><a href="{safe_href}" target="_blank" rel="noopener noreferrer">{safe_text}</a></li>'
                )
            else:
                safe_value = html.escape(value)
                html_parts.append(f"<li>{safe_value}</li>")

        html_parts.append("</ul>")