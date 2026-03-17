class EntitiesReporter:

    def __init__(self, ontology_index):
        self.ontology_index = ontology_index

    def generate_markdown_report(self, results, output_file):

        print("🔥 USING report_markdown_report")

        md = "# Clasificación de entidades turísticas\n\n"

        block_id = 1

        for block in results:

            text = block.get("text", "")[:200]

            md += f"## Bloque {block_id}\n\n"
            md += f"> {text}\n\n"

            md += "| Entidad | Clase | Score | Propiedades ontológicas |\n"
            md += "|--------|-------|-------|--------------------------|\n"

            for entity in block.get("entities", []):

                label = entity.get("entity", "")
                cls = entity.get("class", "")
                score = entity.get("score", 0)

                properties = []

                # ==================================================
                # 🔥 1. PROPIEDADES DEL PIPELINE (PRINCIPAL)
                # ==================================================
                props_dict = entity.get("properties", {})

                if isinstance(props_dict, dict):
                    for k, v in props_dict.items():
                        properties.append(f"{k}: {v}")

                # ==================================================
                # 🔥 2. PROPIEDADES DE ONTOLOGÍA (OPCIONAL)
                # ==================================================
                uri = entity.get("uri")

                if uri and self.ontology_index:
                    try:
                        ont_props = self.ontology_index.get_class_properties(uri)
                        for p in ont_props:
                            prop_name = p["property"].split("#")[-1]

                            # evitar duplicados
                            if prop_name not in properties:
                                properties.append(prop_name)
                    except Exception as e:
                        print("Ontology error:", e)

                # ==================================================
                # FORMATO FINAL
                # ==================================================
                props_str = ", ".join(properties)

                md += f"| {label} | {cls} | {score:.2f} | {props_str} |\n"

            md += "\n"
            block_id += 1

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(md)