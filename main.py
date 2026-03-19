import os
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

print("🔥 ESTE ES MI MAIN.PY REAL")

from src.site_crawler import SiteCrawler
from src.tourism_pipeline import TourismPipeline
from src.graph.kg_builder import KnowledgeGraphBuilder
from src.report.markdown_report import EntitiesReporter
from src.entity_description_consolidator import EntityDescriptionConsolidator


def main():

    print("🔥 DENTRO DE MAIN")

    start_url = "https://turismo.maspalomas.com/"
    ###start_url = "https://turismoapps.dip-badajoz.es/"
    ###start_url = "https://visitsevilla.es/"
    


    print("\n🌍 Iniciando crawling del sitio...\n")

    crawler = SiteCrawler(start_url, max_pages=250)

    pages = crawler.crawl()

    print(f"\n📄 Páginas encontradas: {len(pages)}")

    pipeline = TourismPipeline("src/ontology/core.rdf")

    all_results = []

    # 🔎 procesar páginas
    for url, html in pages:

        print(f"\n🔎 Procesando página: {url}")

        results = pipeline.run(html)

        all_results.extend(results)

    print(f"\n🧠 Total bloques procesados: {len(all_results)}")

    # ---------------------------
    # CONSOLIDACIÓN GLOBAL
    # ---------------------------

    consolidator = EntityDescriptionConsolidator()
    global_entities = consolidator.consolidate(all_results)

    print("\n🌍 ENTIDADES GLOBALES:", len(global_entities))

    # 🔥 RESUMEN GLOBAL (AQUÍ)
    for e in global_entities[:10]:   # limitar a 10 para no saturar
        print("\n---")
        print("Entidad:", e["entity"])
        print("Clase:", e["class"])
        print("Descripción:", e["short_description"])


    consolidator = EntityDescriptionConsolidator()
    global_entities = consolidator.consolidate(all_results)

    print("🌍 ENTIDADES GLOBALES:", len(global_entities))

    # ---------------------------
    # construir Knowledge Graph
    # ---------------------------

    kg_builder = KnowledgeGraphBuilder(pipeline.ontology_index)

    kg_builder.build(all_results)
    kg_builder.save("knowledge_graph.ttl")

    print("\n🧩 Knowledge graph guardado en knowledge_graph.ttl")

    # ---------------------------
    # generar reporte
    # ---------------------------

    reporter = EntitiesReporter(pipeline.ontology_index)

    reporter.generate_markdown_report(all_results, "entities_report.md")




    print("📑 Reporte Markdown generado en entities_report.md")

    print("🔥 ANES DE IF")

if __name__ == "__main__":
        
    print("🔥 ENTRA EN IF")
    main()

    print("🔥 FINAL DEL ARCHIVO")   