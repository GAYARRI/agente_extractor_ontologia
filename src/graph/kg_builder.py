from rdflib import Graph, Namespace, URIRef, Literal
import re
import html


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
    # NORMALIZACIÓN DE ENTIDADES
    # ==================================================

    def normalize_entity(self, label):

        if not label:
            return ""

        label = str(label).lower().strip()

        # quitar caracteres raros
        label = re.sub(r"[^\w\s]", "", label)

        # espacios → _
        label = re.sub(r"\s+", "_", label)

        return label

    # ==================================================
    # NORMALIZACIÓN DE PROPIEDADES
    # ==================================================

    def normalize_property(self, label):
        if not label:
            return ""

        label = str(label).strip()
        label = re.sub(r"[^\w\s]", "", label)
        label = re.sub(r"\s+", "_", label)

        return label

    # ==================================================
    # BUILD DEL GRAFO
    # ==================================================

    def build(self, results):

        for block in results:

            entities = block.get("entities", [])

            for entity in entities:

                label = entity.get("entity")

                if not label:
                    continue

                normalized = self.normalize_entity(label)

                if not normalized:
                    continue

                subject = URIRef(self.EX[normalized])

                # -------------------------
                # LABEL LEGIBLE
                # -------------------------
                self.graph.add((
                    subject,
                    self.TOUR.label,
                    Literal(label)
                ))

                # -------------------------
                # TIPO
                # -------------------------
                entity_class = entity.get("class", "Place")

                self.graph.add((
                    subject,
                    self.TOUR.type,
                    Literal(entity_class)
                ))

                # -------------------------
                # SCORE / CONFIANZA
                # -------------------------
                score = entity.get("score")
                if score is not None:
                    self.graph.add((
                        subject,
                        self.TOUR.score,
                        Literal(score)
                    ))

                # -------------------------
                # URL ORIGEN DEL BLOQUE
                # -------------------------
                block_url = block.get("url")
                if block_url:
                    self.graph.add((
                        subject,
                        self.TOUR.sourceUrl,
                        Literal(block_url)
                    ))

                # -------------------------
                # PROPIEDADES
                # -------------------------
                props = entity.get("properties", {})

                for k, v in props.items():

                    if not k or v is None or v == "":
                        continue

                    pred_name = self.normalize_property(k)
                    if not pred_name:
                        continue

                    pred = self.TOUR[pred_name]

                    if isinstance(v, list):
                        for item in v:
                            if item is None or item == "":
                                continue
                            self.graph.add((
                                subject,
                                pred,
                                Literal(str(item))
                            ))
                    else:
                        # si viniera serializado como "a | b | c", se guarda tal cual
                        self.graph.add((
                            subject,
                            pred,
                            Literal(str(v))
                        ))

                # -------------------------
                # DESCRIPCIONES
                # -------------------------
                short_desc = entity.get("short_description")
                long_desc = entity.get("long_description")

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

                # -------------------------
                # WIKIDATA LINK (si existe)
                # -------------------------
                wikidata_id = entity.get("wikidata_id")

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

            html_parts.append(f'<div class="entity">')
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

        image_props = {"image", "mainImage", "additionalImages"}
        url_like_props = {"url", "sourceUrl", "wikidata", "relatedUrls", "contactUrls"}

        if prop_name in image_props:
            html_parts.append(f'<div class="prop"><strong>{html.escape(prop_name)}:</strong></div>')
            for value in values:
                safe_value = html.escape(str(value))
                html_parts.append(f'<img src="{safe_value}" alt="{html.escape(prop_name)}">')
            return

        if len(values) == 1:
            value = str(values[0])

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
                    f'<a href="{safe_href}" target="_blank">{safe_text}</a></div>'
                )
            else:
                safe_value = html.escape(value)
                html_parts.append(
                    f'<div class="prop"><strong>{html.escape(prop_name)}:</strong> {safe_value}</div>'
                )
            return

        html_parts.append(f'<div class="prop"><strong>{html.escape(prop_name)}:</strong></div>')
        html_parts.append('<ul class="value-list">')

        for value in values:
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
                    f'<li><a href="{safe_href}" target="_blank">{safe_text}</a></li>'
                )
            else:
                safe_value = html.escape(value)
                html_parts.append(f"<li>{safe_value}</li>")

        html_parts.append("</ul>")