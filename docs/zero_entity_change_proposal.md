# Propuesta de Cambios a partir de `zero-entity_ShortList.csv`

Esta propuesta sale de tus anotaciones manuales sobre URLs con `0 entidades`, con una idea central muy clara:

- rescatar mejor falsos negativos en fichas detalle `/lugar/...`
- no materializar entidades en listados si la estrategia correcta es seguir los enlaces
- tratar aparte las paginas institucionales o programaticas que contienen recursos semanticamente validos

## Hallazgos principales

### 1. Muchas fichas `/lugar/...` son falsos negativos claros

Casos validados por ti:
- `/lugar/archivo-real-y-general-de-navarra` -> `Palace`
- `/lugar/catedral-de-santa-maria-la-real` -> `Cathedral`
- `/lugar/catedral-santa-maria-la-real` -> duplicada de la anterior
- `/lugar/capilla-de-san-fermin` -> `Church/Chapel`
- `/lugar/espacio-sanfermin-espazioa` -> `InterpretationCenter`
- `/lugar/ciudadela-y-vuelta-del-castillo` -> `HistoricalOrCulturalResource`
- `/lugar/cicloturismo-eurovelo-1` -> `Route`
- `/lugar/a-bardenas-reales-ribera` -> `NaturalPark`

Conclusión:
- el mayor retorno ahora no está en relajar el filtro global
- está en rescatar mejor detalle pages que hoy se están yendo a `0 entidades`

### 2. Los listados deben seguir siendo conservadores

Casos validados por ti:
- `/en/lugares`
- `/tipo-lugar/lugares-de-interes`
- `/evento`

Conclusión:
- si la pagina es un listado o una pagina-hub de enlaces, no conviene materializar entidades ahí
- la entidad debe salir en la pagina enlazada
- esto confirma que no hay que perseguir “una entidad por pagina”

### 3. Las páginas programáticas/institucionales sí deben producir entidades

Casos validados por ti:
- `/area-profesional/estrategias-y-planes-municipales` -> ~10 entidades
- `/area-profesional/estudios-e-informes` -> ~3 entidades

Conclusión:
- estas paginas no son ruido ni simples listados
- requieren una estrategia de extracción distinta a la de POI físico clásico

### 4. Algunas páginas editoriales/hub son mixtas

Casos:
- `/ayuntamiento`
- `/ayuntamiento/en-familia`
- `/planifica-tu-viaje`

Conclusión:
- no parecen fichas detalle simples
- pero sí pueden contener POIs o servicios enlazados y merecen una revisión por familia

## Cambios propuestos por script

## 1. `src/tourism_pipeline_ontology_driven.py`

### Cambio A. Reforzar el rescate de fichas `/lugar/...`

Ahora mismo muchas de esas URLs terminan en `0 entidades` aunque el contenido es claramente una ficha útil.

Propuesta:
- si la URL cae en familia `/lugar/...` o `/en/lugar/...`, activar un modo `detail_priority`
- en ese modo:
  - dar más peso al `title`, `h1` y al slug
  - relajar ligeramente el descarte cuando haya evidencia de ficha
  - asegurar que el nombre principal de la ficha entre al menos como candidato fuerte

Señales de ficha:
- slug informativo
- `h1` descriptivo
- bloque principal con descripción extensa
- presencia de imagen, dirección, contexto histórico o explicativo

### Cambio B. No cambiar la estrategia conservadora en listados

Tus anotaciones dejan esto bastante claro:
- `/tipo-lugar/...`
- `/en/lugares`
- `/evento`

Propuesta:
- mantenerlos como `listing`
- no materializar entidad principal local salvo evidencia excepcional
- si ya existe navegación hacia fichas detalle, priorizar el seguimiento del enlace

### Cambio C. Añadir una rama de extracción `programmatic_document`

Para:
- `/area-profesional/estrategias-y-planes-municipales`
- `/area-profesional/estudios-e-informes`

Propuesta:
- cuando `pageIntent == programmatic`, extraer candidatos desde:
  - encabezados de bloques
  - títulos de documentos
  - enlaces de descarga
- no tratarlos como POIs físicos
- producir entidades documentales o de recurso turístico semántico

Tu criterio manual sugiere una caída práctica en `TouristResource` o familia equivalente.

## 2. `src/entity_type_resolver.py`

### Cambio D. Añadir patrones más fuertes para clases validadas en fichas detalle

A partir de tu revisión, hay clases que deberían resolverse con mucha más claridad:
- `Cathedral`
- `Chapel` / `Church`
- `Palace`
- `Route`
- `NaturalPark`
- `HistoricalOrCulturalResource`
- `InterpretationCenter`

Propuesta:
- subir el peso del slug y del nombre cuando aparecen pistas como:
  - `catedral`
  - `capilla`
  - `palacio`
  - `eurovelo`
  - `bardenas`
  - `espacio`
  - `archivo`
- no dejar que acaben en `Unknown` o se filtren si la ficha tiene contexto descriptivo fuerte

### Cambio E. Resolver mejor páginas multi-entidad naturales

Casos como:
- `/en/lugar/camino-de-santiago-urederra`
- `/en/lugar/bertiz-valle-de-baztan-zugarramurdi-urdax-bidasoa`

Propuesta:
- si el slug o el `h1` contienen varias entidades coordinadas, permitir un modo `multi_resource_detail`
- en ese modo:
  - aceptar varias entidades
  - no forzar una sola entidad principal

## 3. `src/entities/entity_final_filter.py` o filtro final equivalente

### Cambio F. No sobrefiltrar fichas con contexto denso

Patrón observado:
- páginas claramente válidas con descripciones ricas acaban en `0 entidades`

Propuesta:
- si la página es `detail_priority` y el candidato principal coincide con el `h1` o el slug:
  - exigir menos evidencia para que sobreviva
- pero solo para esa familia, no globalmente

Esto permite subir cobertura sin romper limpieza general.

## 4. `src/entity_resolver.py`

### Cambio G. Deduplicación conservadora de duplicados obvios

Caso validado:
- `catedral-de-santa-maria-la-real`
- `catedral-santa-maria-la-real`

Propuesta:
- si dos fichas tienen nombre casi idéntico y tipo compatible, consolidarlas
- priorizar la URL o la ficha con mejor evidencia, pero sin borrar el rastro de duplicidad

## Estrategia recomendada para la siguiente iteración

### Iteración 1
- rescatar `/lugar/...` y `/en/lugar/...`
- sin tocar umbrales globales
- sin abrir más listados

### Iteración 2
- modo `programmatic_document` para `/area-profesional/...`

### Iteración 3
- revisar páginas mixtas:
  - `/planifica-tu-viaje`
  - `/ayuntamiento`
  - `/ayuntamiento/en-familia`

## Qué no recomiendo hacer

- no bajar umbrales globales para todas las páginas
- no intentar forzar entidad en hubs o listados solo por mejorar el ratio
- no mezclar en la misma iteración rescate de fichas detalle y cambios agresivos en listados

## Prioridad práctica

Si solo hacemos una cosa en la próxima iteración, mi recomendación es esta:

1. rescatar bien `/lugar/...`
2. dejar intacta la política conservadora de listados
3. después abrir una rama específica para páginas programáticas
