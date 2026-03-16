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

            md += "| Entidad | Clase | Score | Propiedades ontológicas |\n"
            md += "|--------|-------|-------|--------------------------|\n"

            for entity in block["entities"]:

                label = entity.get("entity", "")
                cls = entity.get("class", "")
                score = entity.get("score", 0)
                uri = entity.get("uri")

                properties = []

                if uri and self.ontology_index:

                    props = self.ontology_index.get_class_properties(uri)

                    for p in props:

                        prop_name = p["property"].split("#")[-1]
                        properties.append(prop_name)

                props_str = ", ".join(properties)

                md += f"| {label} | {cls} | {score:.2f} | {props_str} |\n"

            md += "\n"

            block_id += 1

        with open(output_file, "w", encoding="utf-8") as f:

            f.write(md)