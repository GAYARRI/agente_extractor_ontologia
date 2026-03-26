import os
import certifi
from dotenv import load_dotenv

load_dotenv()
os.environ["SSL_CERT_FILE"] = certifi.where()

from src.site_crawler import SiteCrawler
from src.tourism_pipeline_ontology_driven import TourismPipeline
from src.knowledge_graph_builder import KnowledgeGraphBuilder
from src.report.markdown_report import EntitiesReporter
from src.entity_description_consolidator import EntityDescriptionConsolidator
from src.export.json_exporter import JSONExporter
from src.visualization.tourism_graph_visualizer import TourismGraphVisualizer
from src.visualization.tourism_map_visualizer import TourismMapVisualizer
from src.kg_postprocessor import KGPostProcessor


def main():
    print("🚀 Iniciando proyecto de extracción ontológica turística")

    start_url = "https://visitasevilla.es/"
    # start_url = "https://turismo.maspalomas.com/"
    # start_url = "https://turismoapps.dip-badajoz.es/"
    # start_url = "https://www.info.valladolid.es/"
    # start_url = "https://www.turismourense.com/"
    # start_url = "https://www.costablanca.org/"

    print(f"\n🌐 Iniciando crawling del sitio: {start_url}\n")

    crawler = SiteCrawler(start_url, max_pages=1)
    pages = crawler.crawl()

    print(f"\n📄 Páginas encontradas: {len(pages)}")

    pipeline = TourismPipeline("src/ontology/core.rdf")
    all_results = []

    for url, html in pages:
        print(f"\n🔎 Procesando página: {url}")
        try:
            results = pipeline.run(html, url=url)

            if isinstance(results, list):
                all_results.extend(results)
            elif results:
                all_results.append(results)

        except Exception as exc:
            print(f"⚠️ Error procesando {url}: {exc}")

    print(f"\n✅ Total resultados intermedios: {len(all_results)}")

    # ---------------------------
    # CONSOLIDACIÓN GLOBAL
    # ---------------------------
    consolidator = EntityDescriptionConsolidator()
    global_entities = consolidator.consolidate(all_results)
    
    postprocessor = KGPostProcessor()
    global_entities = postprocessor.process(global_entities)

    print("\n=== DEBUG IMAGES ===")
    for e in global_entities[:10]:
        print(
            e.get("name") or e.get("entity_name") or e.get("entity"),
            "image=", e.get("image", ""),
            "mainImage=", e.get("mainImage", ""),
            "props.image=", (e.get("properties", {}) or {}).get("image", ""),
            "props.candidateImage=", (e.get("properties", {}) or {}).get("candidateImage", "")
        )

    print("\n=== TRAS EntityDescriptionConsolidator ===")
    if global_entities:
        print(global_entities[0])
    

    print(f"\n🌍 ENTIDADES GLOBALES: {len(global_entities)}")

    for e in global_entities[:5]:
        print("\n---")
        print("Entidad:", e.get("entity") or e.get("entity_name") or e.get("label"))
        print("Clase:", e.get("class") or e.get("type"))
        print("Descripción corta:", e.get("short_description", ""))
        print("Dirección:", e.get("address", ""))
        print("Teléfono:", e.get("phone", ""))
        print("Email:", e.get("email", ""))
        print("Coordenadas:", e.get("coordinates", {"lat": None, "lng": None}))

    # ---------------------------
    # CONSTRUIR KNOWLEDGE GRAPH
    # ---------------------------
    kg_builder = KnowledgeGraphBuilder()
    graph = kg_builder.build_graph(global_entities)
    kg_builder.save_graph(graph, "knowledge_graph.ttl")

    print("\n🧠 Knowledge graph guardado en knowledge_graph.ttl")

    # Si tu builder tiene una función save_html, puedes mantener esto
    if hasattr(kg_builder, "save_html"):
        try:
            kg_builder.save_html("knowledge_graph.html")
            print("🌐 Visualización HTML guardada en knowledge_graph.html")
        except Exception as exc:
            print(f"⚠️ No se pudo generar HTML del KG: {exc}")

    # ---------------------------
    # GENERAR REPORTE
    # ---------------------------
    reporter = EntitiesReporter(pipeline.ontology_index)
    reporter.generate_markdown_report(global_entities, "entities_report.md")
    print("📝 Reporte Markdown generado en entities_report.md")


    # ---------------------------
    # EXPORT JSON
    # ---------------------------
    json_exporter = JSONExporter()
    json_exporter.export(global_entities, "entities.json")
    print("📦 Export JSON generado en entities.json")
     
        # ---------------------------
    # VISUALIZACIONES HTML
    # ---------------------------
    try:
        graph_visualizer = TourismGraphVisualizer()
        graph_visualizer.build_html(global_entities, "tourism_graph.html")
        print("🕸️ Visualización de grafo guardada en tourism_graph.html")
    except Exception as exc:
        print(f"⚠️ No se pudo generar tourism_graph.html: {exc}")

    try:
        map_visualizer = TourismMapVisualizer()
        map_visualizer.build_html(global_entities, "tourism_map.html")
        print("🗺️ Mapa turístico guardado en tourism_map.html")
    except Exception as exc:
        print(f"⚠️ No se pudo generar tourism_map.html: {exc}")  
     

print("ONTOLOGY PATH:", os.path.abspath("src/ontology/core.rdf"))
print("EXISTS:", os.path.exists("src/ontology/core.rdf"))


if __name__ == "__main__":
    main()