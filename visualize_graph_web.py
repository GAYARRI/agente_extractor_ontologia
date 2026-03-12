from rdflib import Graph, RDF
from pyvis.network import Network

print("Cargando Knowledge Graph...")

g = Graph()
g.parse("knowledge_graph.ttl", format="turtle")

net = Network(
    height="800px",
    width="100%",
    bgcolor="#ffffff",
    directed=True
)

# física más estable
net.barnes_hut()

# -----------------------------
# colores por tipo
# -----------------------------

colors = {
    "Place": "#4CAF50",
    "Event": "#E53935",
    "Museum": "#1E88E5",
    "Hotel": "#FB8C00",
    "Restaurant": "#8E24AA",
    "Volcano": "#6D4C41",
    "Theater": "#3949AB",
    "TourismEntity": "#9E9E9E"
}

# -----------------------------
# nodos añadidos
# -----------------------------

added_nodes = {}

print("Procesando triples...")

for s, p, o in g:

    s_name = str(s).split("/")[-1]
    p_name = str(p).split("/")[-1]
    o_name = str(o).split("/")[-1]

    # tipo de nodo
    node_color = "#9E9E9E"

    if p_name == "type":
        node_color = colors.get(o_name, "#9E9E9E")

    if s_name not in added_nodes:
        net.add_node(
            s_name,
            label=s_name,
            color=node_color,
            size=25
        )
        added_nodes[s_name] = True

    if o_name not in added_nodes:
        net.add_node(
            o_name,
            label=o_name,
            size=20
        )
        added_nodes[o_name] = True

    net.add_edge(
        s_name,
        o_name,
        label=p_name,
        color="#666"
    )

print("Generando visualización...")

net.write_html("tourism_graph.html")

print("Visualización creada: tourism_graph.html")