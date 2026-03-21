class EntitiesReporter:
    def __init__(self, ontology_index):
        self.ontology_index = ontology_index

    def _safe(self, value):
        if value is None:
            return ""
        if isinstance(value, list):
            return " | ".join(str(v) for v in value)
        return str(value).replace("\n", " ").replace("|", ", ")

    def generate_markdown_report(self, results, output_file):
        md = "# Clasificación de entidades turísticas\n\n"

        for i, block in enumerate(results, 1):
            text = block.get("text", "")[:200]
            page_url = block.get("url", "")

            md += f"## Bloque {i}\n\n"
            if page_url:
                md += f"**URL origen:** {page_url}\n\n"

            md += f"> {text}\n\n"
            md += "| Entidad | Clase | Imagen principal | Score | Descripción corta | Descripción larga | Propiedades |\n"
            md += "|--------|-------|------------------|-------|------------------|------------------|-------------|\n"

            for entity in block.get("entities", []):
                name = self._safe(entity.get("entity", ""))
                cls = self._safe(entity.get("class", ""))
                score = entity.get("score", 0)
                props = entity.get("properties", {})

                image = props.get("mainImage") or props.get("image", "")
                image_md = f"![img]({image})" if image else ""

                short_desc = self._safe(entity.get("short_description", ""))
                long_desc = self._safe(entity.get("long_description", ""))

                if not short_desc:
                    short_desc = self._safe(text[:120])

                if not long_desc:
                    long_desc = self._safe(text[:200])

                props_str_parts = []
                for k, v in props.items():
                    if k in ("image", "mainImage"):
                        continue
                    if k == "additionalImages" and isinstance(v, list):
                        props_str_parts.append(f"{k}: {len(v)} imágenes adicionales")
                        continue  

                    props_str_parts.append(f"{k}: {self._safe(v)}")

                props_str = "; ".join(props_str_parts)

                md += (
                    f"| {name} | {cls} | {image_md} | {score:.2f} | "
                    f"{short_desc} | {long_desc} | {props_str} |\n"
                )

            md += "\n"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md)