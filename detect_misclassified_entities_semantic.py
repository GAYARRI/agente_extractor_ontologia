from rdflib import Graph, RDF
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

INPUT_GRAPH = "knowledge_graph.ttl"
OUTPUT_REPORT = "entities_to_fix.md"

print("Cargando Knowledge Graph...")

g = Graph()
g.parse(INPUT_GRAPH, format="turtle")

entities = {}

for s, p, o in g:

    if p == RDF.type:

        entity = str(s).split("/")[-1]
        class_name = str(o).split("/")[-1]

        entities[entity] = class_name


# -----------------------------
# clases ontológicas principales
# -----------------------------

ontology_classes = [
    "Place",
    "Event",
    "Museum",
    "Restaurant",
    "Hotel",
    "Volcano",
    "Beach",
    "Theater",
    "TouristAttractionSite"
]

print("Cargando modelo de embeddings...")

model = SentenceTransformer("all-MiniLM-L6-v2")

print("Generando embeddings de clases...")

class_embeddings = model.encode(ontology_classes)


def predict_class(entity):

    entity_embedding = model.encode([entity])

    sims = cosine_similarity(entity_embedding, class_embeddings)[0]

    best_idx = np.argmax(sims)

    return ontology_classes[best_idx], sims[best_idx]


print("Analizando entidades...")

suggestions = []

for entity, current_class in entities.items():

    if current_class == "TourismEntity":

        predicted, score = predict_class(entity)

        if score > 0.45:

            suggestions.append({
                "entity": entity,
                "current": current_class,
                "suggested": predicted,
                "score": float(score)
            })


print("Generando reporte...")

with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:

    f.write("# Entities Possibly Misclassified\n\n")

    for s in suggestions:

        f.write(f"- **{s['entity']}**\n")
        f.write(f"  - current: {s['current']}\n")
        f.write(f"  - suggested: {s['suggested']}\n")
        f.write(f"  - confidence: {s['score']:.2f}\n\n")

print("Reporte generado:", OUTPUT_REPORT)