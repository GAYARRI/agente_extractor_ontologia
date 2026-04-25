# Propuesta de Cambios a partir de `iteration_sample_autodraft_1`

Esta propuesta sale de los casos anotados manualmente en `outputs/iteration_sample_autodraft_1.csv`.

## Objetivo general

Corregir errores por familias de comportamiento y no por URL individual:

1. ignorar paginas tecnicas o legales
2. mejorar la clasificacion de intencion de pagina
3. reducir clases genericas como `Location`
4. reforzar entidades institucionales o programaticas sin romper fichas validas

## Patrones detectados en la muestra

### 1. Paginas que deben ignorarse

Casos marcados:
- `https://visitpamplonairuna.com/?elementor_library=privilegio-de-la-union`
- `https://visitpamplonairuna.com/aviso-legal`

Conclusión:
- hace falta una capa de exclusión temprana por URL y señales de página

## 2. Paginas institucionales o programaticas con falso negativo

Casos marcados:
- `/area-profesional/estrategias-y-planes-municipales`
- `/area-profesional/estudios-e-informes`
- `/area-profesional/licitaciones`

Conclusión:
- el sistema actual no está distinguiendo bien entre `pagina institucional vacia` y `pagina institucional con recursos semanticos`
- aquí no parece que la acción correcta sea “ignorar”, sino producir entidades semánticas agregadas o documentales

## 3. Paginas con clase demasiado generica

Casos marcados:
- `/area-profesional` -> `Location`
- `/en/lugar/archivo-real-y-general-de-navarra` -> `Location`
- `/en/lugar/pump-track` -> `Location`
- `/en/lugar/skate-park-antoniutti` -> `Location`
- `/plan-de-sostenibilidad-turistica` -> `Location`

Conclusión:
- `Location` está sobreviviendo demasiado lejos en el pipeline
- hay que convertir `Location` en señal intermedia, no en clase final normal

## 4. Entidades institucionales mal resueltas

Casos marcados:
- `/area-profesional/noticias-pstd-sf365` -> `TownHall`
- `/ayuntamiento/en-familia` -> `Event`

Conclusión:
- se están promoviendo menciones contextuales a clases finales demasiado concretas
- el sistema necesita diferenciar mejor entre `entidad principal de la pagina` y `menciones contextuales`

## 5. Entidad canónica validada

Caso marcado:
- `/en/lugar/ayuntamiento` -> `TownHall` correcto

Conclusión:
- esta URL debe ser la referencia canónica para deduplicar otras menciones del ayuntamiento

## Cambios propuestos por script

## 1. `src/tourism_pipeline_ontology_driven.py`

### Cambio A. Clasificador temprano de intención de página

Añadir una función específica tipo:
- `_classify_page_intent(...) -> legal | technical | detail | listing | institutional | programmatic`

Reglas iniciales:
- `legal` si URL o título contiene `aviso-legal`, `cookies`, `privacidad`, `accesibilidad`
- `technical` si URL contiene `elementor_library`, parámetros técnicos, plantillas, librerías o endpoints internos
- `institutional/programmatic` si contiene combinaciones como `area-profesional`, `planes`, `estrategias`, `informes`, `licitaciones`, `sostenibilidad`

Uso:
- si `legal` o `technical`, devolver `[]` antes de extraer entidades
- si `institutional/programmatic`, cambiar estrategia de extracción y tipado

### Cambio B. Filtro duro de URLs ignorables

Añadir una lista de patrones de exclusión temprana:
- `aviso-legal`
- `elementor_library`
- `privacy`
- `cookies`
- `accesibilidad`

Esto debe ejecutarse antes de la extracción de bloques.

### Cambio C. Soporte explícito a páginas institucionales

No recomiendo volver al cambio agresivo anterior, pero sí una versión más contenida:
- si la página es `institutional/programmatic`, no asumir POI físico por defecto
- generar solo candidatos desde encabezados o bloques principales
- luego pasarlos por clasificación con clases candidatas como:
  - `TourismEntity`
  - `PublicService`
  - `TourismOrganisation`
  - `Promotion`

Muy importante:
- no suprimir automáticamente entidades por tener enlaces
- solo cambiar el modo de priorización

### Cambio D. Evitar que listados o hubs se queden con la clase principal

Para páginas como `/area-profesional`, la entidad principal no debe salir como `Location`.

Si la página es `listing` o `institutional`:
- penalizar clases genéricas
- exigir evidencia contextual más fuerte para promover una única entidad principal
- permitir varias entidades si el contenido realmente es multi-recurso

## 2. `src/entity_type_resolver.py`

### Cambio E. `Location` no debe ser salida final salvo excepción

Ahora mismo ya se trata como clase débil en varios puntos, pero sigue sobreviviendo.

Propuesta:
- endurecer la regla: si la clase final resuelta es `Location`, forzar una segunda ronda con:
  - texto completo de página
  - URL
  - título
  - h1
  - breadcrumbs
- si tras esa segunda ronda no hay clase específica:
  - en páginas legales/técnicas: descartar
  - en páginas institucionales: caer a `TourismEntity` o `PublicService`
  - en páginas detalle: dejar revisión o descarte según evidencia

### Cambio F. Reforzar patrones específicos ya presentes

Has marcado dos casos concretos que el resolver ya conoce parcialmente:
- `pump-track`
- `skate-park`

Hay que revisar por qué no están ganando las reglas de `SportsCenter` o similar.

Acciones:
- subir peso de patrones `pump track`, `skate park`, `skatepark`, `deporte sobre ruedas`
- dar más peso al slug y al título cuando coinciden con esos patrones

### Cambio G. Mejor tratamiento de patrimonio histórico

Caso:
- `archivo-real-y-general-de-navarra`

Propuesta:
- añadir pistas de patrimonio para `Archive`, `HistoricalBuilding`, `Monument` o la clase más cercana disponible
- si no existe clase exacta, priorizar la familia cultural/histórica antes que `Location`

## 3. `src/entity_filter.py` y `src/entities/entity_final_filter.py`

### Cambio H. Descartar páginas legales aunque contengan nombres capitalizados

Caso:
- `aviso-legal`

Propuesta:
- si `page_signals` indica página legal, el filtro debe descartar todas las entidades salvo whitelist explícita

### Cambio I. Filtrar la entidad principal incorrecta en páginas institucionales

Caso:
- `noticias-pstd-sf365` clasificado como `TownHall`
- `en-familia` clasificado como `Event`

Propuesta:
- si la mención principal es una institución genérica o una categoría editorial y la página contiene varios recursos subordinados, no promoverla como única entidad principal

## 4. `src/entity_resolver.py`

### Cambio J. Canonicalización explícita del Ayuntamiento

Sin recuperar la lógica que revertimos, sí propondría algo más acotado:
- mantener una lista de entidades ancla conocidas cuando la URL de detalle sea inequívoca
- si aparece una mención compatible en otra página, preferir fusionarla con la ficha canónica

Caso validado:
- `https://visitpamplonairuna.com/en/lugar/ayuntamiento`

Esta mejora debe ser conservadora y basada en similitud alta + tipo compatible.

## 5. `outputs/suggest_iteration_sample.py`

### Cambio K. Mejorar la preselección automática

Tu anotación muestra que la herramienta ya detecta muchos casos útiles.

Mejora propuesta:
- añadir grupos explícitos:
  - `legal/technical ignore`
  - `institutional false negative`
  - `generic location`
  - `canonical entity validation`

Así la siguiente muestra saldrá aún más orientada a reglas generales.

## Orden recomendado de implementación

Para no mezclar demasiadas cosas, haría estas iteraciones:

### Iteración 1
- filtro duro legal/técnico
- clasificador de intención de página
- descarte temprano de `elementor_library` y `aviso-legal`

### Iteración 2
- endurecer `Location` como clase final
- reforzar `pump-track`, `skate-park`, patrimonio histórico

### Iteración 3
- modo específico para páginas institucionales o programáticas
- mejor promoción de entidades agregadas

### Iteración 4
- canonicalización/deduplicación conservadora del `Ayuntamiento`

## Información adicional que convendría preparar

Antes de implementar, sería ideal tener 5-10 casos más por cada grupo:

- legales/técnicos
- institucionales con 0 entidades
- detalles que salen como `Location`
- entidades institucionales mal promovidas

Con eso podemos convertir esta propuesta en cambios más seguros y medibles.
