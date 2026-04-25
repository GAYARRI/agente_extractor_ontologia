# Plantilla de Iteracion de Mejora

Usa esta plantilla para preparar cada iteracion de mejora del extractor sin depender de revisar pagina por pagina de forma improvisada.

## 1. Objetivo de la iteracion

- Fecha:
- Nombre corto de la iteracion:
- Problema principal a atacar:
- Criterio de exito:
- Riesgo aceptable:

Ejemplos de problema principal:
- Reducir duplicados entre paginas de listado y paginas detalle
- Mejorar clasificacion de paginas institucionales o programaticas
- Reducir falsos positivos en paginas editoriales
- Mejorar recall de eventos

Ejemplos de criterio de exito:
- Menos duplicados sin perder POIs validos
- Las paginas institucionales deben producir `PublicService` o `TourismOrganisation`
- Las paginas de listado no deben generar entidades finales si existe ficha de detalle

## 2. Muestra de URLs

Incluye entre 10 y 20 URLs por iteracion. Mejor pocas y representativas que muchas sin revisar.

| ID | URL | Familia de pagina | Esperado | Actual | Tipo de error |
| --- | --- | --- | --- | --- | --- |
| 1 |  | listado / detalle / institucional / evento / legal / editorial |  |  | falso positivo / falso negativo / mal clasificado / duplicado / ruido |
| 2 |  |  |  |  |  |
| 3 |  |  |  |  |  |

## 3. Resultado esperado por URL

Describe el comportamiento correcto de forma concreta.

| ID | Debe extraer entidades | Cuantas | Clase o clases esperadas | Debe ignorarse | Debe seguir enlaces |
| --- | --- | ---: | --- | --- | --- |
| 1 | si / no | 0 |  | si / no | si / no |
| 2 |  |  |  |  |  |
| 3 |  |  |  |  |  |

Notas:
- Si una pagina es de listado, indica si debe crear solo candidatos o entidades finales.
- Si una pagina es institucional, indica si quieres `PublicService`, `TourismService`, `TourismOrganisation`, etc.

## 4. Evidencia de salida actual

Pega aqui lo minimo necesario para comparar.

### Resumen global actual

- Paginas procesadas:
- Paginas con entidades:
- Paginas sin entidades:
- Entidades totales:
- Clases principales detectadas:

### Casos problematicos observados

| ID | Entidad actual | Clase actual | URL actual | Por que esta mal |
| --- | --- | --- | --- | --- |
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |

## 5. Hipotesis de mejora

Aqui definimos la regla o cambio general que creemos que puede arreglar el problema.

- Hipotesis:
- Capa afectada:
- Impacto esperado:
- Riesgo de regresion:

Capas posibles:
- clasificacion de pagina
- extraccion de candidatos
- tipado o clasificacion
- deduplicacion
- enriquecimiento
- filtros finales

## 6. Regresion minima a comprobar

Incluye siempre algunos casos que no queremos romper.

| ID | URL | Que no debe romperse |
| --- | --- | --- |
| R1 |  |  |
| R2 |  |  |
| R3 |  |  |

## 7. Comparacion antes vs despues

Rellenar despues de aplicar cambios.

### Metricas

| Metrica | Antes | Despues | Cambio |
| --- | ---: | ---: | --- |
| Paginas con entidades |  |  |  |
| Paginas sin entidades |  |  |  |
| Entidades totales |  |  |  |
| Duplicados estimados |  |  |  |
| Falsos positivos en la muestra |  |  |  |
| Falsos negativos en la muestra |  |  |  |
| Casos bien clasificados en la muestra |  |  |  |

### Evaluacion por muestra

| ID | Antes | Despues | Resultado |
| --- | --- | --- | --- |
| 1 |  |  | mejora / igual / empeora |
| 2 |  |  |  |
| 3 |  |  |  |

## 8. Decision final

- Se conserva el cambio: si / no
- Se necesita otra iteracion: si / no
- Siguiente problema a atacar:
- Observaciones:

## 9. Recomendacion de uso

Para cada iteracion, idealmente comparteme solo esto:

1. Objetivo principal
2. Tabla de 10-20 URLs
3. Esperado por URL
4. Casos actuales mal resueltos
5. Criterio de exito

Con esa informacion podemos mejorar por patrones y no por casuistica aislada.
