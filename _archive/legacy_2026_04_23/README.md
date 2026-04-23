# Legacy Archive 2026-04-23

Este directorio contiene archivos movidos fuera del flujo activo del proyecto el 23 de abril de 2026.

## Por que existe este archivo

Durante la limpieza del repositorio se detectaron modulos, scripts y utilidades que ya no intervenian directamente en la ejecucion principal definida por:

- [main.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/main.py)
- [src/tourism_pipeline_ontology_driven.py](c:/Viual_Studio_V/Tourism_Ontology_Agent/src/tourism_pipeline_ontology_driven.py)

En lugar de borrarlos, se movieron aqui para:

- simplificar el arbol principal del repo
- reducir confusion entre codigo activo y codigo historico
- conservar referencia por si algun modulo antiguo sigue siendo util

## Que tipo de archivos hay aqui

Este archive incluye, entre otros:

- extractores antiguos o duplicados
- builders RDF o visualizadores previos
- scripts auxiliares de analisis o validacion no usados en el flujo actual
- utilidades de prueba

## Criterio de archivado

Los archivos movidos no aparecian integrados de forma activa en el flujo principal o estaban claramente sustituidos por versiones nuevas.

Ejemplos:

- `src/tourism_entity_extracto.py` frente a `src/tourism_entity_extractor.py`
- `src/event_detector.py` frente a `src/events/event_detector.py`
- `src/reporting/entities_reporter.py` frente a `src/report/markdown_report.py`
- `src/graph/kg_builder.py` frente a `src/knowledge_graph_builder.py`

## Importante

Archivar no significa necesariamente que el archivo sea inutil. Significa que, a fecha `2026-04-23`, no forma parte del flujo activo principal y se ha apartado para clarificar el proyecto.
