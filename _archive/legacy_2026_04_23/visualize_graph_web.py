from rdflib import Graph, RDF, RDFS
from pyvis.network import Network


KG_FILE = "knowledge_graph.ttl"
OUTPUT_HTML = "knowledge_graph.html"


def local_name(uri):
    text = str(uri)
    if "#" in text:
        return text.split("#")[-1]
    return text.split("/")[-1]


def build_labels(graph):
    labels = {}
    for s, _, o in graph.triples((None, RDFS.label, None)):
        labels[str(s)] = str(o)
    return labels


def main():
    g = Graph()
    g.parse(KG_FILE, format="turtle")

    labels = build_labels(g)

    net = Network(
        height="900px",
        width="100%",
        bgcolor="#ffffff",
        font_color="black",
        directed=True,
    )

    added_nodes = set()

    for s, p, o in g:
        # ignoramos labels como aristas visuales
        if p == RDFS.label:
            continue

        s_id = str(s)
        p_label = local_name(p)

        if s_id not in added_nodes:
            s_label = labels.get(s_id, local_name(s))
            net.add_node(
                s_id,
                label=s_label,
                title=f"URI: {s_id}",
            )
            added_nodes.add(s_id)

        if p == RDF.type:
            o_id = str(o)
            if o_id not in added_nodes:
                o_label = local_name(o)
                net.add_node(
                    o_id,
                    label=o_label,
                    title=f"Clase: {o_id}",
                    shape="box",
                )
                added_nodes.add(o_id)

            net.add_edge(s_id, o_id, label="type")
            continue

        # si el objeto es literal
        if not hasattr(o, "startswith") and getattr(o, "datatype", None) is not None or getattr(o, "language", None) is not None:
            literal_id = f"{s_id}-{p_label}-{str(o)}"
            if literal_id not in added_nodes:
                net.add_node(
                    literal_id,
                    label=str(o)[:60],
                    title=f"Literal: {str(o)}",
                    shape="dot",
                )
                added_nodes.add(literal_id)

            net.add_edge(s_id, literal_id, label=p_label)
            continue

        # si el objeto es URIRef
        o_id = str(o)
        if str(o).startswith("http://") or str(o).startswith("https://"):
            if o_id not in added_nodes:
                o_label = labels.get(o_id, local_name(o))
                net.add_node(
                    o_id,
                    label=o_label,
                    title=f"URI: {o_id}",
                )
                added_nodes.add(o_id)

            net.add_edge(s_id, o_id, label=p_label)
        else:
            literal_id = f"{s_id}-{p_label}-{str(o)}"
            if literal_id not in added_nodes:
                net.add_node(
                    literal_id,
                    label=str(o)[:60],
                    title=f"Literal: {str(o)}",
                    shape="dot",
                )
                added_nodes.add(literal_id)

            net.add_edge(s_id, literal_id, label=p_label)

    net.toggle_physics(True)
    net.write_html(OUTPUT_HTML, open_browser=False, notebook=False)
    print(f"Visualización guardada en {OUTPUT_HTML}")


if __name__ == "__main__":
    main()