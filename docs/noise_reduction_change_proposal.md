# Noise Reduction Change Proposal

## Objetivo

Reducir ruido sin perder el salto de cobertura logrado en la ultima ejecucion.

Prioridades:

1. cortar entidades de interfaz o servicio incrustadas en nombres
2. cortar entidades narrativas o contextuales laterales en fichas detalle
3. tratar paginas programaticas `/area-profesional/...` con una rama especifica
4. despues, atacar `Unknown` utiles por familias

## 1. UI / Service Phrases

### Problema

Se estan promoviendo nombres contaminados por texto de interfaz:

- `Museo de Educacion Ambiental Preguntas`
- `Reservar Si`
- `Ciudad Deportiva Aranzadi Preguntas`
- `Marco Topo Informacion`
- `Maria Informacion`

### Cambio propuesto

Tocar [src/tourism_pipeline_ontology_driven.py](C:/Viual_Studio_V/Tourism_Ontology_Agent/src/tourism_pipeline_ontology_driven.py):

- ampliar `_is_contextual_noise_entity(...)`
- ampliar `_is_detail_secondary_label(...)`
- endurecer `_clean_candidate_name(...)` para cortar sufijos como:
  - `preguntas`
  - `informacion`
  - `reserva`
  - `reservar`
  - `como llegar`
  - `horarios`
  - `tarifas`

Tocar [src/entities/entity_final_filter.py](C:/Viual_Studio_V/Tourism_Ontology_Agent/src/entities/entity_final_filter.py):

- anadir rechazo explicito de nombres que terminen en esos tokens UI
- pero sin rechazar la entidad si tras limpiar queda un nombre valido

### Regla general

Si el nombre parece `entidad + etiqueta operativa`, limpiar primero.  
Si al limpiar no queda una entidad clara, rechazar.

## 2. Narrative Side Entities

### Problema

En fichas ricas o rutas narrativas se estan materializando entidades contextuales:

- `River Forest High School`
- `Primera Guerra Mundial`
- `Elizabeth Hadley Richardson`
- `Pamplona Lauren Bacall`
- `Constitorial Narra Jake Barnes`

### Cambio propuesto

Tocar [src/tourism_pipeline_ontology_driven.py](C:/Viual_Studio_V/Tourism_Ontology_Agent/src/tourism_pipeline_ontology_driven.py):

- anadir una heuristica `_is_narrative_side_entity(...)`
- aplicarla en:
  - `_entity_name_penalty(...)`
  - `_rescue_empty_page_candidates(...)`
  - `_apply_final_filter(...)`

### Señales para marcar como narrativa lateral

- aparece persona o institucion secundaria no alineada con el `slug`
- aparece en paginas `route` o `story-like`
- contiene marcadores narrativos:
  - `narra`
  - `cerca`
  - `adentrate`
  - `descubre`
- el nombre no coincide con `title`, `h1` ni `slug`
- y tampoco es una entidad patrimonial fuerte del destino

### Regla general

En fichas detalle, privilegiar:

- entidad principal de la ficha
- subentidades turisticas claras y visitables

Penalizar:

- personas citadas
- contexto historico general
- referencias biograficas o narrativas

## 3. Programmatic Pages

### Problema

Paginas `/area-profesional/...` ya estan extrayendo, pero con clases fisicas absurdas:

- `Garden`
- `Monument`

### Cambio propuesto

Tocar [src/tourism_pipeline_ontology_driven.py](C:/Viual_Studio_V/Tourism_Ontology_Agent/src/tourism_pipeline_ontology_driven.py):

- reforzar `_classify_page_intent(...)` para distinguir:
  - `programmatic`
  - `institutional_news`
  - `professional_listing`

- si `pageIntent == programmatic`:
  - bajar peso de clases fisicas como `Garden`, `Monument`, `Square`, `Cathedral`
  - priorizar una familia controlada:
    - `TourismService`
    - `PublicService`
    - `DestinationExperience`
    - `HistoricalOrCulturalResource` solo si el nombre lo justifica
    - `Unknown` si no hay clase buena todavia

Tocar [src/ontology_utils.py](C:/Viual_Studio_V/Tourism_Ontology_Agent/src/ontology_utils.py):

- anadir aliases mas seguros para tipos programaticos, evitando que caigan en clases fisicas

### Regla general

En `/area-profesional/...` no inferir lugares fisicos salvo evidencia muy fuerte.

## 4. Unknown Families

### Problema

Hay muchos `Unknown`, pero no todos son igual de urgentes.

### Subfamilias mas rentables

- gastronomia y producto:
  - `Pimientos del Piquillo`
  - `Sidra Navarra`
  - `Queso Roncal`
  - `Torta de Txantxigorri`

- servicios utiles:
  - `Consignas de Correos`

- eventos sectoriales:
  - `CEIN Startup Day`
  - `Simposio Internacional Avances`

### Cambio propuesto

Tocar [src/tourism_pipeline_ontology_driven.py](C:/Viual_Studio_V/Tourism_Ontology_Agent/src/tourism_pipeline_ontology_driven.py) y/o [src/entity_type_resolver.py](C:/Viual_Studio_V/Tourism_Ontology_Agent/src/entity_type_resolver.py):

- crear reglas por familia semantica amplia, no por URL
- ejemplos:
  - productos gastronomicos protegidos -> `HistoricalOrCulturalResource` o clase gastronomica valida si existe
  - consignas / lockers / guarda equipajes -> `PublicService`
  - congresos / simposios / jornadas -> `Event`

## Orden recomendado de implementacion

1. `ui_or_service_phrase`
2. `narrative_side_entity`
3. `programmatic_misclassified`
4. `Unknown` por familias

## Criterio de exito

- bajar `Unknown` de `121`
- bajar inflacion de `Monument`
- limpiar nombres contaminados (`Preguntas`, `Informacion`, `Reserva`)
- mantener una cobertura alta, evitando volver al escenario de baja extraccion
