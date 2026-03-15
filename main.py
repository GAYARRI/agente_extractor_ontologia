from src.tourism_pipeline import TourismPipeline
from src.tourism_crawler import TourismCrawler
from src.graph.kg_builder import KnowledgeGraphBuilder


def main():

    start_url = "https://turismoapps.dip-badajoz.es/"

    crawler = TourismCrawler(
        start_url=start_url,
        max_pages=5
    )

    pages = crawler.crawl()

    pipeline = TourismPipeline("ontology/core.rdf")

    all_results = []

    for url, html in pages:

        print("\nProcesando:", url)

        results = pipeline.run(html)

        all_results.extend(results)

    # crear knowledge graph correctamente
    kg = KnowledgeGraphBuilder(
        ontology_index=pipeline.classifier.matcher.index,
        source_page=start_url
    )

    kg.add_results(all_results)

    kg.save("knowledge_graph.ttl")

    print("\nKnowledge graph construido con", len(all_results), "bloques")


if __name__ == "__main__":
    main()