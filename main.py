import os
import certifi
from dotenv import load_dotenv
load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()

from src.site_crawler import SiteCrawler
from src.tourism_pipeline import TourismPipeline
from src.graph.kg_builder import KnowledgeGraphBuilder
from src.report.markdown_report import EntitiesReporter
from src.entity_description_consolidator import EntityDescriptionConsolidator


def main():
    print("🚀 Iniciando proyecto de extracción ontológica turística")

    start_url = "https://visitasevilla.es/"
    # start_url = "https://turismo.maspalomas.com/"
    # start_url = "https://turismoapps.dip-badajoz.es/"

    print(f"\n🌐 Iniciando crawling del sitio: {start_url}\n")

    crawler = SiteCrawler(start_url, max_pages=500)
    pages = crawler.crawl()

    print(f"\n📄 Páginas encontradas: {len(pages)}")

    pipeline = TourismPipeline("src/ontology/core.rdf")
    all_results = []

    for url, html in pages:
        print(f"\n🔎 Procesando página: {url}")
        try:
            results = pipeline.run(html, url=url)
            all_results.extend(results)
        except Exception as exc:
            print(f"⚠️ Error procesando {url}: {exc}")

    print(f"\n✅ Total bloques procesados: {len(all_results)}")

    # ---------------------------
    # CONSOLIDACIÓN GLOBAL
    # ---------------------------
    consolidator = EntityDescriptionConsolidator()
    global_entities = consolidator.consolidate(all_results)

    print(f"\n🌍 ENTIDADES GLOBALES: {len(global_entities)}")

    for e in global_entities[:3]:
        print("\n---")
        print("Entidad:", e.get("entity"))
        print("Clase:", e.get("class"))
        print("Descripción:", e.get("short_description"))

    # ---------------------------
    # CONSTRUIR KNOWLEDGE GRAPH
    # ---------------------------
    kg_builder = KnowledgeGraphBuilder(pipeline.ontology_index)
    kg_builder.build(all_results)
    kg_builder.save("knowledge_graph.ttl")
    print("\n🧠 Knowledge graph guardado en knowledge_graph.ttl")

    if hasattr(kg_builder, "save_html"):
        kg_builder.save_html("knowledge_graph.html")
        print("🌐 Visualización HTML guardada en knowledge_graph.html")

    # ---------------------------
    # GENERAR REPORTE
    # ---------------------------
    reporter = EntitiesReporter(pipeline.ontology_index)
    reporter.generate_markdown_report(all_results, "entities_report.md")
    print("📝 Reporte Markdown generado en entities_report.md")


if __name__ == "__main__":
    main()