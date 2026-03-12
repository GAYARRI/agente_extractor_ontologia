from rdflib import Graph, RDF
from collections import defaultdict

INPUT_GRAPH = "knowledge_graph.ttl"
OUTPUT_REPORT = "entities_to_fix.md"

print("Cargando grafo...")

g = Graph()
g.parse(INPUT_GRAPH, format="turtle")

entities = {}
classes = {}

print("Extrayendo entidades...")

for s, p, o in g:

    if p == RDF.type:
        entity = str(s).split("/")[-1]
        class_name = str(o).split("/")[-1]

        entities[entity] = class_name


# -----------------------------------
# heurísticas simples de clasificación
# -----------------------------------

rules = {
    "Event": ["festival", "carnaval", "tour", "concierto"],
    "Theater": ["teatro"],
    "Museum": ["museo"],
    "Restaurant": ["restaurante"],
    "Hotel": ["hotel"],
    "Volcano": ["teide", "volcán"],
    "Place": ["sevilla", "santa cruz", "laguna", "tenerife"]
}


def guess_class(entity):

    e = entity.lower()

    for c, words in rules.items():

        for w in words:

            if w in e:
                return c

    return None


# -----------------------------------
# detectar errores
# -----------------------------------

print("Analizando entidades...")

suggestions = []

for entity, class_name in entities.items():

    if class_name == "TourismEntity":

        predicted = guess_class(entity)

        if predicted:

            suggestions.append((entity, class_name, predicted))


# -----------------------------------
# generar reporte
# -----------------------------------

print("Generando reporte...")

with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:

    f.write("# Entities Possibly Misclassified\n\n")

    for entity, current, predicted in suggestions:

        f.write(f"- **{entity}**\n")
        f.write(f"  - current: {current}\n")
        f.write(f"  - suggested: {predicted}\n\n")

print("Reporte generado:", OUTPUT_REPORT)