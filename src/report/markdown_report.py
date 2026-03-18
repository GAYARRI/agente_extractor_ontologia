class EntitiesReporter:

    def __init__(self, ontology_index):
        self.ontology_index = ontology_index

    def generate_markdown(self, results, output_file):

        md = "# Clasificación de entidades turísticas\n\n"

        block_id = 1

        for block in results:

            text = block.get("text", "")[:200]

            md += f"## Bloque {block_id}\n\n"
            md += f"> {text}\n\n"

            md += "| Entidad | Clase | Imagen | Score | Descripcion corta | Propiedades ontológicas |\n"
            md += "|--------|-------|--------|-------|------------------|--------------------------|\n"

            for entity in block["entities"]:

                label = entity.get("entity", "")
                cls = entity.get("class", "")
                score = entity.get("score", 0)

                props = entity.get("properties", {})

                # 🔥 EXTRAER IMAGEN
                image_url = props.get("image", "")

                if image_url:
                    image_md = f"![img]({image_url})"
                else:
                    image_md = ""

                # 🔥 DESCRIPCIÓN
                short_desc = entity.get("short_description", "")

                # 🔥 PROPIEDADES SIN IMAGE
                properties = []
                for k, v in props.items():

                    if k == "image":
                        continue

                    properties.append(f"{k}: {v}")

                props_str = ", ".join(properties)

                md += f"| {label} | {cls} | {image_md} | {score:.2f} | {short_desc} | {props_str} |\n"

            md += "\n"
            block_id += 1

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md)