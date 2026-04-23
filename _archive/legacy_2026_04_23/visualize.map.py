from rdflib import Graph
import folium

print("Cargando Knowledge Graph...")

g = Graph()
g.parse("knowledge_graph.ttl", format="turtle")

# mapa centrado en Canarias
map = folium.Map(location=[28.3, -16.6], zoom_start=10)

entities = {}

print("Extrayendo coordenadas...")

for s, p, o in g:

    s = str(s)
    p = str(p).split("/")[-1]
    o = str(o)

    if p == "geoLat":

        entities.setdefault(s, {})["lat"] = float(o)

    if p == "geoLong":

        entities.setdefault(s, {})["lon"] = float(o)

for entity, data in entities.items():

    if "lat" in data and "lon" in data:

        name = entity.split("/")[-1]

        folium.Marker(
            location=[data["lat"], data["lon"]],
            popup=name,
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(map)

print("Creando mapa...")

map.save("tourism_map.html")

print("Mapa creado: tourism_map.html")