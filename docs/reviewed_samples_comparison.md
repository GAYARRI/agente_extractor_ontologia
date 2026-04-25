# Comparison Against Reviewed Samples

## Iteration Sample

- `resolved`: `2`
- `pending`: `3`
- `review`: `9`

### Pending Or Regression

- `pending` | https://visitpamplonairuna.com/area-profesional/estrategias-y-planes-municipales
  Esperado: falso negativo confirmado
  Actual: 4 | Garden, Unknown
- `pending` | https://visitpamplonairuna.com/area-profesional/estudios-e-informes
  Esperado: falso negativo confirmado
  Actual: 5 | Monument, Unknown
- `pending` | https://visitpamplonairuna.com/area-profesional/licitaciones
  Esperado: falso negativo confirmado
  Actual: 6 | Garden

## Zero-Entity Shortlist

- `resolved`: `7`
- `pending`: `10`
- `regression`: `3`

### Pending Or Regression

- `pending` | https://visitpamplonairuna.com/lugar/archivo-real-y-general-de-navarra
  Esperado: Palace | 1 entity
  Actual: 0 | 0 entidades
- `pending` | https://visitpamplonairuna.com/lugar/catedral-de-santa-maria-la-real
  Esperado: Cathedral | 1entity
  Actual: 0 | 0 entidades
- `pending` | https://visitpamplonairuna.com/lugar/catedral-santa-maria-la-real
  Esperado: Cathedral | 1 entity
  Actual: 0 | 0 entidades
- `pending` | https://visitpamplonairuna.com/lugar/capilla-de-san-fermin
  Esperado: Church/ Chapel | 2 entities
  Actual: 0 | 0 entidades
- `pending` | https://visitpamplonairuna.com/lugar/espacio-sanfermin-espazioa
  Esperado: InterpretationCenter | 1 entity
  Actual: 0 | 0 entidades
- `pending` | https://visitpamplonairuna.com/lugar/ciudadela-y-vuelta-del-castillo
  Esperado: HistoricalOrCulturalResource | 1 entity
  Actual: 0 | 0 entidades
- `pending` | https://visitpamplonairuna.com/lugar/cicloturismo-eurovelo-1
  Esperado: Route | 1 entity
  Actual: 0 | 0 entidades
- `pending` | https://visitpamplonairuna.com/lugar/a-bardenas-reales-ribera
  Esperado: NaturalPark | 1entity
  Actual: 0 | 0 entidades
- `regression` | https://visitpamplonairuna.com/en/lugares
  Esperado: Es un listado de Hoteles y espacios | 0 entities
  Actual: 3 | Hotel
- `regression` | https://visitpamplonairuna.com/area-profesional/estrategias-y-planes-municipales
  Esperado: Todas ellas son TouristResources | 10 entities
  Actual: 4 | Garden, Unknown
- `regression` | https://visitpamplonairuna.com/ayuntamiento/en-familia
  Esperado: Pagina informativa de pois para turismo familiar | >0 entities
  Actual: 5 | Cathedral, Event, Palace, Stadium
- `pending` | https://visitpamplonairuna.com/en/lugar/bertiz-valle-de-baztan-zugarramurdi-urdax-bidasoa
  Esperado: NaturalResources | 4 entities
  Actual: 0 | 0 entidades
- `pending` | https://visitpamplonairuna.com/en/lugar/camino-de-santiago-urederra
  Esperado: NaturalResources / Monuments | 5 entities
  Actual: 0 | 0 entidades
