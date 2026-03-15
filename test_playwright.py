# debug_ttl.py
from rdflib import Graph

path = "ontology/core.ttl"

with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

buffer = ""

for i, line in enumerate(lines, 1):
    buffer += line
    try:
        g = Graph()
        g.parse(data=buffer, format="turtle")
    except Exception as e:
        print("Error cerca de la línea:", i)
        print(line)
        break