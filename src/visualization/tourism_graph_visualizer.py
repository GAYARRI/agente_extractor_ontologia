# src/visualization/tourism_graph_visualizer.py

from pyvis.network import Network


class TourismGraphVisualizer:
    def __init__(self):
        pass

    def build_html(self, entities, output_path="tourism_graph.html"):
        net = Network(height="900px", width="100%", bgcolor="#ffffff", font_color="#222222", directed=False)

        added_nodes = set()

        for e in entities or []:
            name = (
                e.get("entity_name")
                or e.get("entity")
                or e.get("label")
                or e.get("name")
                or ""
            ).strip()

            if not name:
                continue

            if name not in added_nodes:
                etype = e.get("class") or e.get("type") or "Entity"
                desc = e.get("short_description") or e.get("long_description") or ""
                title = f"<b>{name}</b><br>Tipo: {etype}<br>{desc}"
                net.add_node(name, label=name, title=title)
                added_nodes.add(name)

            related = e.get("relatedUrls", [])
            if isinstance(related, str):
                related = [x.strip() for x in related.split("|") if x.strip()]

            for url in related:
                url_node = f"URL::{url}"
                if url_node not in added_nodes:
                    net.add_node(url_node, label="link", title=url, shape="dot", size=8)
                    added_nodes.add(url_node)
                net.add_edge(name, url_node, title="relatedUrl")

        net.set_options("""
        {
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -3000,
              "springLength": 150
            }
          },
          "nodes": {
            "shape": "dot",
            "size": 18,
            "font": {
              "size": 14
            }
          },
          "edges": {
            "smooth": true
          }
        }
        """)

        net.write_html(output_path)