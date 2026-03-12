import os
import warnings
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from rdflib import Graph, RDF, RDFS, OWL
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

KG_FILE = "knowledge_graph.ttl"
ONTOLOGY_FILE = "ontology/core.ttl"
OUTPUT_REPORT = "entities_to_fix.md"

print("Cargando Knowledge Graph...")

kg = Graph()
kg.parse(KG_FILE, format="turtle")

print("Cargando ontología...")

ontology = Graph()

with open(ONTOLOGY_FILE, "rb") as f:
    ontology.parse(file=f, format="xml")

# -----------------------------
# extraer clases de la ontología
# -----------------------------

print("Extrayendo clases ontológicas...")

ontology_classes = []

for s, p, o in ontology:

    if p == RDF.type and o == OWL.Class:

        class_name = str(s).split("#")[-1].split("/")[-1]

        if class_name and not class_name.startswith("N"):
            ontology_classes.append(class_name)

ontology_classes = list(set(ontology_classes))

print("Clases encontradas:", len(ontology_classes))

# -----------------------------
# cargar entidades del KG
# -----------------------------

entities = {}

for s, p, o in kg:

    if p == RDF.type:

        entity = str(s).split("/")[-1]
        class_name = str(o).split("/")[-1]

        entities[entity] = class_name

# -----------------------------
# cargar modelo de embeddings
# -----------------------------

print("Cargando modelo de embeddings...")

model = SentenceTransformer("all-MiniLM-L6-v2")

print("Generando embeddings de clases...")

class_embeddings = model.encode(ontology_classes)


def predict_class(entity):

    entity_embedding = model.encode([entity])

    sims = cosine_similarity(entity_embedding, class_embeddings)[0]

    best_idx = np.argmax(sims)

    return ontology_classes[best_idx], sims[best_idx]


# -----------------------------
# analizar entidades
# -----------------------------

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
                "confidence": float(score)
            })

# -----------------------------
# generar reporte
# -----------------------------

print("Generando reporte...")

with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:

    f.write("# Entities Possibly Misclassified\n\n")

    for s in suggestions:

        f.write(f"### {s['entity']}\n")
        f.write(f"- current class: `{s['current']}`\n")
        f.write(f"- suggested class: `{s['suggested']}`\n")
        f.write(f"- confidence: `{s['confidence']:.2f}`\n\n")

print("Reporte generado:", OUTPUT_REPORT)