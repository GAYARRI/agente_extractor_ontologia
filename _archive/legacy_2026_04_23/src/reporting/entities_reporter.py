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

                # 🔥 PROPIEDADES DEL PIPELINE (CLAVE)
                props_dict = entity.get("properties", {})

                props_list = []

                if isinstance(props_dict, dict):
                    for k, v in props_dict.items():
                        props_list.append(f"{k}: {v}")

                # 🔥 (OPCIONAL) añadir ontología si existe
                uri = entity.get("uri")

                if uri and self.ontology_index:
                    try:
                        ont_props = self.ontology_index.get_class_properties(uri)
                        for p in ont_props:
                            prop_name = p["property"].split("#")[-1]
                            if prop_name not in props_list:
                                props_list.append(prop_name)
                    except:
                        pass

                props_str = ", ".join(props_list)

                md += f"| {label} | {cls} | {score:.2f} | {props_str} |\n"

            md += "\n"
            block_id += 1

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md)