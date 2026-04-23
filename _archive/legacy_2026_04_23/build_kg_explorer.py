from rdflib import Graph, RDF
from collections import defaultdict
import os

INPUT_GRAPH = "knowledge_graph.ttl"
OUTPUT_DIR = "kg_docs"

print("Cargando Knowledge Graph...")

g = Graph()
g.parse(INPUT_GRAPH, format="turtle")

entities_by_class = defaultdict(list)
properties = defaultdict(list)

for s, p, o in g:

    s_name = str(s).split("/")[-1]
    p_name = str(p).split("/")[-1]
    o_name = str(o).split("/")[-1]

    if p == RDF.type:

        entities_by_class[o_name].append(s_name)

    else:

        properties[s_name].append((p_name, o_name))


os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------------------------
# index
# ------------------------------------------------

index_html = f"""
<html>
<head>
<title>Tourism Knowledge Graph</title>
</head>
<body>

<h1>Tourism Knowledge Graph Explorer</h1>

<ul>
<li><a href="classes.html">Browse Classes</a></li>
<li><a href="entities.html">Browse Entities</a></li>
<li><a href="../tourism_graph.html">Graph Visualization</a></li>
</ul>

</body>
</html>
"""

open(f"{OUTPUT_DIR}/index.html", "w", encoding="utf-8").write(index_html)

# ------------------------------------------------
# classes
# ------------------------------------------------

classes_html = "<h1>Classes</h1><ul>"

for cls in sorted(entities_by_class):

    classes_html += f"<li>{cls} ({len(entities_by_class[cls])})</li>"

classes_html += "</ul>"

open(f"{OUTPUT_DIR}/classes.html", "w", encoding="utf-8").write(classes_html)

# ------------------------------------------------
# entities
# ------------------------------------------------

entities_html = "<h1>Entities</h1>"

for cls in sorted(entities_by_class):

    entities_html += f"<h2>{cls}</h2>"

    for ent in entities_by_class[cls]:

        entities_html += f"<h3>{ent}</h3><ul>"

        if ent in properties:

            for prop, val in properties[ent]:

                entities_html += f"<li>{prop}: {val}</li>"

        entities_html += "</ul>"

open(f"{OUTPUT_DIR}/entities.html", "w", encoding="utf-8").write(entities_html)

print("Explorador generado en:", OUTPUT_DIR)