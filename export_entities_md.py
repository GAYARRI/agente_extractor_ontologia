from collections import defaultdict
from rdflib import Graph, RDF, RDFS, URIRef, Literal

KG_FILE = "knowledge_graph.ttl"
OUTPUT_MD = "entities_graph.md"


def local_name(node):
    text = str(node)
    if "#" in text:
        return text.split("#")[-1]
    return text.split("/")[-1]


def safe_mermaid_id(text: str) -> str:
    return (
        text.replace(" ", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .replace(",", "")
        .replace(".", "")
        .replace(":", "")
        .replace("/", "_")
    )


def load_graph(path):
    g = Graph()
    g.parse(path, format="turtle")
    return g


def build_labels(graph):
    labels = {}
    for s, _, o in graph.triples((None, RDFS.label, None)):
        labels[str(s)] = str(o)
    return labels


def get_node_label(node, labels):
    if str(node) in labels:
        return labels[str(node)]
    return local_name(node)


def is_entity_uri(node):
    return isinstance(node, URIRef)


def extract_entity_data(graph):
    labels = build_labels(graph)

    entity_types = defaultdict(list)
    data_properties = defaultdict(list)
    object_relations_out = defaultdict(list)
    object_relations_in = defaultdict(list)
    all_entities = set()

    for s, p, o in graph:
        if not isinstance(s, URIRef):
            continue

        all_entities.add(s)

        if p == RDF.type and isinstance(o, URIRef):
            entity_types[s].append(get_node_label(o, labels))
            continue

        if p == RDFS.label:
            continue

        if isinstance(o, Literal):
            data_properties[s].append((local_name(p), str(o)))
        elif isinstance(o, URIRef):
            all_entities.add(o)
            object_relations_out[s].append((local_name(p), o))
            object_relations_in[o].append((local_name(p), s))

    return {
        "labels": labels,
        "entities": sorted(all_entities, key=lambda x: get_node_label(x, labels).lower()),
        "types": entity_types,
        "data_properties": data_properties,
        "out_relations": object_relations_out,
        "in_relations": object_relations_in,
    }


def build_mermaid(data, max_edges=80):
    labels = data["labels"]
    out_relations = data["out_relations"]

    lines = ["```mermaid", "graph TD"]

    added_nodes = set()
    edge_count = 0

    for subj, rels in out_relations.items():
        subj_label = get_node_label(subj, labels)
        subj_id = safe_mermaid_id(subj_label)

        if subj_id not in added_nodes:
            lines.append(f'    {subj_id}["{subj_label}"]')
            added_nodes.add(subj_id)

        for predicate, obj in rels:
            if edge_count >= max_edges:
                break

            obj_label = get_node_label(obj, labels)
            obj_id = safe_mermaid_id(obj_label)

            if obj_id not in added_nodes:
                lines.append(f'    {obj_id}["{obj_label}"]')
                added_nodes.add(obj_id)

            lines.append(f"    {subj_id} -->|{predicate}| {obj_id}")
            edge_count += 1

        if edge_count >= max_edges:
            break

    lines.append("```")
    return "\n".join(lines)


def export_markdown(data, output_path):
    labels = data["labels"]
    entities = data["entities"]
    entity_types = data["types"]
    data_properties = data["data_properties"]
    out_relations = data["out_relations"]
    in_relations = data["in_relations"]

    md = []
    md.append("# Tourism Knowledge Graph Preview\n")
    md.append(f"Total entidades/recursos detectados: **{len(entities)}**\n")

    md.append("<details>")
    md.append("<summary><strong>Ver grafo general</strong></summary>\n")
    md.append(build_mermaid(data))
    md.append("\n</details>\n")

    for entity in entities:
        entity_label = get_node_label(entity, labels)
        types = entity_types.get(entity, [])
        props = data_properties.get(entity, [])
        rels_out = out_relations.get(entity, [])
        rels_in = in_relations.get(entity, [])

        md.append("<details>")
        md.append(f"<summary><strong>{entity_label}</strong></summary>\n")

        md.append(f"- **URI:** `{str(entity)}`")

        if types:
            md.append(f"- **Tipo(s):** {', '.join(sorted(set(types)))}")
        else:
            md.append("- **Tipo(s):** No tipado")

        if props:
            md.append("- **Propiedades:**")
            for prop, value in sorted(props, key=lambda x: x[0].lower()):
                clean_value = value.replace("\n", " ").strip()
                md.append(f"  - **{prop}** → {clean_value}")

        if rels_out:
            md.append("- **Relaciones salientes:**")
            for pred, obj in sorted(rels_out, key=lambda x: (x[0].lower(), get_node_label(x[1], labels).lower())):
                md.append(f"  - **{pred}** → {get_node_label(obj, labels)}")

        if rels_in:
            md.append("- **Relaciones entrantes:**")
            for pred, subj in sorted(rels_in, key=lambda x: (x[0].lower(), get_node_label(x[1], labels).lower())):
                md.append(f"  - {get_node_label(subj, labels)} → **{pred}**")

        md.append("\n</details>\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


def main():
    graph = load_graph(KG_FILE)
    data = extract_entity_data(graph)
    export_markdown(data, OUTPUT_MD)
    print(f"Markdown generado en: {OUTPUT_MD}")


if __name__ == "__main__":
    main()