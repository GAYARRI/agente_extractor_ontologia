def generate_markdown_report(results, output_path, ontology_index):

    lines = []

    lines.append("# Clasificación de entidades turísticas\n")

    block_id = 1

    for block in results:

        text = block.get("text", "")
        entities = block.get("entities", [])

        if not entities:
            continue

        lines.append(f"## Bloque {block_id}\n")

        preview = text.replace("\n", " ")[:200]

        lines.append(f"> {preview}\n")

        lines.append("| Entidad | Clase | Score | Propiedades ontológicas |")
        lines.append("|--------|-------|-------|-------------------------|")

        for entity in entities:

            name = entity.get("entity", "")
            label = entity.get("class", "")
            score = entity.get("score", 0.0)

            props = ""

            # obtener propiedades ontológicas si la clase existe
            if label and label != "Unknown":

                class_props = ontology_index.get_class_properties(label)

                if class_props:
                    props = ", ".join(class_props)

            lines.append(
                f"| {name} | {label} | {score:.2f} | {props} |"
            )

        lines.append("\n")

        block_id += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))