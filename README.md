# Tourism Ontology Agent

Pipeline de extraccion, normalizacion y enriquecimiento de entidades turisticas a partir de paginas web, con salida en JSON, Markdown, RDF/Turtle y visualizaciones HTML.

## Que hace este proyecto

Este repositorio toma una URL o un sitio web de turismo y construye una representacion estructurada de las entidades detectadas:

- POIs y recursos turisticos como museos, plazas, puentes, catedrales, jardines o estaciones
- eventos y actividades
- tipos ontologicos alineados con la ontologia de turismo
- propiedades enriquecidas como descripcion, imagenes, enlaces, coordenadas y Wikidata
- un knowledge graph exportable en `Turtle`

El objetivo no es solo extraer nombres, sino producir un conjunto de entidades mas limpio y util para exploracion, auditoria y evaluacion.

## Flujo principal

La entrada principal es [main.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/main.py).

El flujo activo, a alto nivel, es:

1. `SiteCrawler` recupera paginas desde una URL o dominio.
2. `TourismPipeline` procesa cada pagina y extrae candidatos.
3. El pipeline limpia, normaliza, puntua, deduplica y resuelve tipos ontologicos.
4. Se enriquecen propiedades como descripcion, imagenes, relaciones, coordenadas y Wikidata.
5. Se exportan resultados en:
   - `entities.json`
   - `entities_report.md`
   - `knowledge_graph.ttl`
   - `tourism_graph.html`
   - `tourism_map.html`

## Modulos principales

- [main.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/main.py): punto de entrada, CLI y generacion de outputs
- [src/tourism_pipeline_ontology_driven.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/tourism_pipeline_ontology_driven.py): pipeline principal
- [src/tourism_entity_extractor.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/tourism_entity_extractor.py): extraccion inicial de entidades
- [src/entity_type_resolver.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/entity_type_resolver.py): resolucion conservadora de tipos
- [src/ontology_matcher.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/ontology_matcher.py): matching contra la ontologia
- [src/knowledge_graph_builder.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/knowledge_graph_builder.py): construccion del knowledge graph RDF
- [src/linking/wikidata_linker.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/linking/wikidata_linker.py): linking y enriquecimiento desde Wikidata
- [src/visualization/tourism_graph_visualizer.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/visualization/tourism_graph_visualizer.py): visualizacion de grafo
- [src/visualization/tourism_map_visualizer.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/visualization/tourism_map_visualizer.py): visualizacion en mapa

## Estructura del repositorio

```text
.
|- main.py
|- src/
|  |- tourism_pipeline_ontology_driven.py
|  |- tourism_entity_extractor.py
|  |- entity_type_resolver.py
|  |- knowledge_graph_builder.py
|  |- ontology/
|  |- entities/
|  |- semantic/
|  |- linking/
|  |- visualization/
|  |- evaluation/
|  `- report/
|- entity_processing/
|- entity_audit/
|- scripts/
|- benchmark/
|- Destinos/
|- data/
|- cache/
`- _archive/
```

## Como ejecutarlo

Ejemplo basico sobre una unica URL:

```bash
python main.py --url "https://visitasevilla.es/"
```

Ejemplo sobre crawling de un sitio:

```bash
python main.py --start_url "https://visitasevilla.es/" --max_pages 10
```

Ejemplo con salida JSON por stdout:

```bash
python main.py --url "https://visitasevilla.es/" --json_stdout
```

Estimacion rapida del tamano potencial de un sitio a partir de `robots.txt` y `sitemaps`:

```bash
python scripts/estimate_site_size.py --start_url "https://www.spain.info/es/"
```

Por defecto, tanto el estimador como el crawler restringen el alcance a la rama del `start_url`.
Si arrancas en `https://www.spain.info/es/`, se contaran y rastrearan solo URLs bajo `/es/`.

Agrupacion por prefijos de URL para ver que secciones pesan mas:

```bash
python scripts/estimate_site_size.py --start_url "https://www.spain.info/es/" --prefix_depth 2 --top_prefixes 20
```

Calculo rapido del porcentaje de entidades fisicas con coordenadas:

```bash
python scripts/coords_pct.py
```

Argumentos importantes:

- `--ontology_path`: ontologia local o alias
- `--url`: procesa una sola pagina
- `--start_url`: lanza crawling del sitio
- `--max_pages`: limita el numero de paginas
- `--expected_type`: sesgo opcional de tipo esperado
- `--kg_output`, `--json_output`, `--report_output`: rutas de salida

## Outputs generados

Despues de una ejecucion normal, el proyecto puede generar:

- `entities.json`: entidades finales exportadas
- `entities_report.md`: reporte legible para inspeccion manual
- `knowledge_graph.ttl`: knowledge graph RDF en Turtle
- `tourism_graph.html`: visualizacion del grafo
- `tourism_map.html`: mapa con entidades geolocalizadas

## Evaluacion y benchmark

Hay utilidades para benchmark y evaluacion en:

- [scripts/generate_predictions_from_benchmark.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/scripts/generate_predictions_from_benchmark.py)
- [scripts/evaluate_predictions.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/scripts/evaluate_predictions.py)
- [scripts/evaluate.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/scripts/evaluate.py)
- [scripts/split_ground_truth.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/scripts/split_ground_truth.py)
- [benchmark/ground_truth.json](c:/Viual_Studio_V/Tourism_Ontology_Agent/benchmark/ground_truth.json)

## Estado del repositorio

El repositorio ha ido acumulando modulos experimentales y utilidades historicas. Para simplificar el flujo activo, parte del codigo que ya no interviene directamente en la ejecucion principal se ha movido a:

- [_archive/legacy_2026_04_23](c:/Viual_Studio_V/Tourism_Ontology_Agent/_archive/legacy_2026_04_23)

Ese directorio conserva herramientas, builders, extractores y visualizadores antiguos que pueden servir como referencia, pero no forman parte del flujo principal actual.

## Dependencias

El fichero base es [requirements.txt](c:/Viual_Studio_V/Tourism_Ontology_Agent/requirements.txt), aunque el proyecto actual usa tambien algunas librerias adicionales en partes del pipeline y benchmarking, por ejemplo:

- `rdflib`
- `beautifulsoup4`
- `trafilatura`
- `requests`
- `python-dotenv`
- `openai`
- `numpy`
- `scikit-learn`
- `sentence-transformers`
- `pyvis`
- `folium`

Si vas a reproducir el pipeline completo, conviene revisar imports reales en `src/` y complementar el entorno.

## Notas

- La ontologia principal del proyecto esta en [src/ontology/core.rdf](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/ontology/core.rdf)
- El proyecto contiene outputs, caches y datasets de trabajo dentro del mismo repositorio
- Parte del codigo y de los datos aun conserva rastros de problemas de encoding historicos; varias iteraciones recientes han ido corrigiendo esto en el flujo activo

## Siguiente mejora recomendada

Dos mejoras naturales para seguir endureciendo el repo:

1. consolidar dependencias reales en un `requirements` mas fiel al pipeline actual
2. separar claramente `codigo fuente`, `datasets`, `outputs generados` y `archivos legacy`
