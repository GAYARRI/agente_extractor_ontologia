# src/visualization/tourism_map_visualizer.py

import folium


class TourismMapVisualizer:
    def __init__(self, default_lat=37.3891, default_lng=-5.9845, default_zoom=12):
        self.default_lat = default_lat
        self.default_lng = default_lng
        self.default_zoom = default_zoom

    def build_html(self, entities, output_path="tourism_map.html"):
        coords_entities = []

        for e in entities or []:
            coords = e.get("coordinates") or {}
            lat = coords.get("lat")
            lng = coords.get("lng")

            if lat is None or lng is None:
                continue

            try:
                lat = float(lat)
                lng = float(lng)
            except Exception:
                continue

            coords_entities.append((e, lat, lng))

        if coords_entities:
            center_lat = sum(lat for _, lat, _ in coords_entities) / len(coords_entities)
            center_lng = sum(lng for _, _, lng in coords_entities) / len(coords_entities)
        else:
            center_lat = self.default_lat
            center_lng = self.default_lng

        fmap = folium.Map(location=[center_lat, center_lng], zoom_start=self.default_zoom)

        for e, lat, lng in coords_entities:
            name = (
                e.get("entity_name")
                or e.get("entity")
                or e.get("label")
                or e.get("name")
                or "Entidad"
            )
            etype = e.get("class") or e.get("type") or "Entity"
            desc = e.get("short_description") or ""

            popup = f"<b>{name}</b><br>Tipo: {etype}<br>{desc}"
            folium.Marker(
                location=[lat, lng],
                popup=popup,
                tooltip=name
            ).add_to(fmap)

        if not coords_entities:
            folium.Marker(
                location=[self.default_lat, self.default_lng],
                popup="No hay entidades con coordenadas disponibles",
                tooltip="Sin coordenadas"
            ).add_to(fmap)

        fmap.save(output_path)