# Paquete de Geolocalizacion de Entidades Fisicas

Este paquete extrae coordenadas geograficas para entidades fisicas detectadas en paginas web turisticas.

## Que incluye

- `geo_utils/tourism_property_extractor.py`
  Extrae coordenadas embebidas en la propia pagina.
- `geo_utils/nominatim_resolver.py`
  Hace fallback externo con Wikidata y Nominatim cuando la pagina no trae coordenadas.
- `geo_utils/entity_geo_locator.py`
  Orquesta ambos pasos y devuelve un resultado unificado.
- `example_usage.py`
  Ejemplo minimo de uso.

## Flujo de trabajo

El paquete trabaja en dos fases:

1. Extraccion local desde la pagina
   Busca coordenadas en:
   - JSON-LD
   - atributos `data-lat` / `data-lng`
   - `iframe` de mapas
   - fragmentos JavaScript
   - regex sobre HTML o texto

2. Fallback por resolucion geografica
   Si la pagina no trae coordenadas y la entidad parece fisica, intenta resolverlas con:
   - Wikidata
   - Nominatim

## Cuando usar cada modulo

- Si ya tienes `html` y quieres intentar sacar coordenadas directas:
  usa `TourismPropertyExtractor`.
- Si tienes nombre y direccion y quieres resolver coordenadas aunque no esten en la pagina:
  usa `HybridGeoResolver`.
- Si quieres el comportamiento completo del proyecto:
  usa `EntityGeoLocator`.

## Instalacion

```bash
pip install -r requirements.txt
```

## Ejemplo rapido

```python
from geo_utils import EntityGeoLocator

locator = EntityGeoLocator(default_city="Madrid")

result = locator.locate(
    entity={
        "name": "Museo Casa Botines",
        "class": "Museum",
    },
    html=html,
    text=page_text,
    url="https://www.ejemplo.es/recurso/casa-botines",
)

print(result)
```

Salida esperada:

```python
{
    "coordinates": {"lat": 42.598, "lng": -5.567},
    "latitude": 42.598,
    "longitude": -5.567,
    "geo_source": "jsonld"
}
```

## Estructura del resultado

El localizador devuelve:

- `coordinates`: diccionario con `lat` y `lng`
- `latitude`
- `longitude`
- `geo_source`: `jsonld`, `data-attrs`, `iframe`, `map-js`, `regex`, `wikidata` o `nominatim`
- `geo_query`: solo si ha habido fallback externo
- `wikidata_id`: si la resolucion vino de Wikidata

## Recomendaciones de uso

- Para portales espanoles, el extractor descarta coordenadas claramente fuera de Espana.
- Nominatim debe usarse con respeto:
  - deja el `min_delay_seconds`
  - configura un `user_agent` identificable
- Conviene conservar el directorio `cache/` para evitar consultas repetidas.

## Dependencias externas

- `requests`
- `beautifulsoup4`

## Relacion con el proyecto principal

Este paquete esta derivado de estas piezas del repositorio original:

- `src/tourism_property_extractor.py`
- `src/nominatim_resolver.py`
- parte de la logica de `src/tourism_pipeline_ontology_driven.py`

