class EntitiesReporter:

    def __init__(self, ontology_index):
        self.ontology_index = ontology_index

    def generate_markdown_report(self, results, output_file):

        md = "# Clasificación de entidades turísticas\n\n"

        for i, block in enumerate(results, 1):

            text = block.get("text", "")[:200]

            md += f"## Bloque {i}\n\n"
            md += f"> {text}\n\n"

            md += "| Entidad | Clase | Imagen | Score | Descripción corta | Descripción larga | Propiedades |\n"
            md += "|--------|-------|--------|-------|------------------|------------------|-------------|\n"

            for entity in block["entities"]:

                name = entity.get("entity", "")
                cls = entity.get("class", "")
                score = entity.get("score", 0)

                props = entity.get("properties", {})

                # 🔥 imagen
                image = props.get("image", "")
                image_md = f"![img]({image})" if image else ""

                # 🔥 descripciones
                short_desc = entity.get("short_description", "")
                long_desc = entity.get("long_description", "")

                # 🔥 fallback (MUY IMPORTANTE)
                if not short_desc:
                    short_desc = text[:120]

                if not long_desc:
                    long_desc = text[:200]

                # 🔥 propiedades
                props_str = ", ".join([
                    f"{k}: {v}" for k, v in props.items() if k != "image"
                ])

                # 🔥 FIX AQUÍ (incluye long_desc)
                md += f"| {name} | {cls} | {image_md} | {score:.2f} | {short_desc} | {long_desc} | {props_str} |\n"

            md += "\n"

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md)