from rdflib import Graph, RDF
from collections import defaultdict, Counter

INPUT_GRAPH = "knowledge_graph.ttl"
OUTPUT_MD = "kg_report.md"

print("Cargando Knowledge Graph...")

g = Graph()
g.parse(INPUT_GRAPH, format="turtle")

entities_by_class = defaultdict(list)
properties = defaultdict(list)
relations = []

# -------------------------
# recorrer triples
# -------------------------

for s, p, o in g:

    s_name = str(s).split("/")[-1]
    p_name = str(p).split("/")[-1]
    o_name = str(o).split("/")[-1]

    if p == RDF.type:

        entities_by_class[o_name].append(s_name)

    else:

        properties[s_name].append((p_name, o_name))
        relations.append((s_name, p_name, o_name))


# -------------------------
# estadísticas
# -------------------------

num_entities = len(set([e for cls in entities_by_class for e in entities_by_class[cls]]))
num_classes = len(entities_by_class)
num_relations = len(relations)

class_counts = Counter()

for cls in entities_by_class:
    class_counts[cls] = len(entities_by_class[cls])

# entidades con coordenadas
geo_entities = []

for ent in properties:

    props = [p for p, v in properties[ent]]

    if "geoLat" in props and "geoLong" in props:
        geo_entities.append(ent)

# -------------------------
# generar markdown
# -------------------------

print("Generando reporte...")

with open(OUTPUT_MD, "w", encoding="utf-8") as f:

    f.write("# Tourism Knowledge Graph Report\n\n")

    # summary
    f.write("## Summary\n\n")
    f.write(f"- Entities: **{num_entities}**\n")
    f.write(f"- Classes: **{num_classes}**\n")
    f.write(f"- Relations: **{num_relations}**\n\n")

    f.write("---\n\n")

    # top classes
    f.write("## Top Classes\n\n")

    for cls, count in class_counts.most_common(10):

        f.write(f"- {cls} ({count})\n")

    f.write("\n---\n\n")

    # entidades con coordenadas
    f.write("## Entities with Coordinates\n\n")

    for e in geo_entities:

        f.write(f"- {e}\n")

    f.write("\n---\n\n")

    # catálogo de entidades
    f.write("# Entity Catalogue\n\n")

    for cls in sorted(entities_by_class):

        f.write(f"## {cls}\n\n")

        for ent in sorted(entities_by_class[cls]):

            f.write(f"### {ent}\n")

            if ent in properties:

                for prop, val in properties[ent]:

                    f.write(f"- {prop}: {val}\n")

            f.write("\n")

print("Reporte generado:", OUTPUT_MD)