from rdflib import Graph, RDF
from collections import defaultdict

INPUT_GRAPH = "knowledge_graph.ttl"
OUTPUT_MD = "entities.md"

g = Graph()
g.parse(INPUT_GRAPH, format="turtle")

entities_by_class = defaultdict(list)
properties = defaultdict(list)

# recorrer triples
for s, p, o in g:

    s_name = str(s).split("/")[-1]
    p_name = str(p).split("/")[-1]
    o_name = str(o).split("/")[-1]

    if p == RDF.type:

        entities_by_class[o_name].append(s_name)

    else:

        properties[s_name].append((p_name, o_name))


with open(OUTPUT_MD, "w", encoding="utf-8") as f:

    f.write("# Tourism Knowledge Graph Entities\n\n")

    for cls in sorted(entities_by_class):

        f.write(f"## {cls}\n\n")

        for ent in sorted(entities_by_class[cls]):

            f.write(f"### {ent}\n")

            if ent in properties:

                for prop, val in properties[ent]:

                    f.write(f"- {prop}: {val}\n")

            f.write("\n")

print("Markdown generado:", OUTPUT_MD)