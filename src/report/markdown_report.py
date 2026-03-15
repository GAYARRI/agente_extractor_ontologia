class MarkdownReport:

    def save(self, results, path="entities_report.md"):

        with open(path, "w", encoding="utf-8") as f:

            f.write("# Clasificación de entidades turísticas\n\n")

            if not results:
                f.write("No se detectaron bloques procesables.\n")
                return

            for i, block in enumerate(results, 1):

                text = block.get("text", "")[:300]

                f.write(f"## Bloque {i}\n\n")
                f.write(f"> {text}\n\n")

                entities = block.get("entities", [])

                if not entities:
                    f.write("No se detectaron entidades.\n\n")
                    continue

                f.write("| Entidad | Clase | Score |\n")
                f.write("|--------|-------|-------|\n")

                for e in entities:

                    entity = e["entity"]
                    label = e["class"]
                    score = f'{e["score"]:.2f}'

                    f.write(f"| {entity} | {label} | {score} |\n")

                f.write("\n")