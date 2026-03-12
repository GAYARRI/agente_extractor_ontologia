import rdflib
import folium

from rdflib import URIRef

GRAPH_FILE = "knowledge_graph.ttl"

print("Cargando grafo...")

g = rdflib.Graph()
g.parse(GRAPH_FILE, format="turtle")

lat_pred = URIRef("http://tourismkg.com/property/latitude")
lon_pred = URIRef("http://tourismkg.com/property/longitude")
name_pred = URIRef("http://tourismkg.com/property/name")

locations = []

for s, p, o in g:

    if p == lat_pred:

        lat = float(o)

        for _, _, lon in g.triples((s, lon_pred, None)):

            lon = float(lon)

            name = str(s).split("/")[-1]

            for _, _, n in g.triples((s, name_pred, None)):
                name = str(n)

            locations.append((name, lat, lon))

print("Entidades geográficas:", len(locations))

if not locations:
    print("No se encontraron coordenadas")
    exit()

# centro del mapa
center_lat = locations[0][1]
center_lon = locations[0][2]

m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

for name, lat, lon in locations:

    folium.Marker(
        location=[lat, lon],
        popup=name,
        icon=folium.Icon(color="blue")
    ).add_to(m)

m.save("tourism_map.html")

print("Mapa generado: tourism_map.html")