# entity_audit

Refactor del script original de auditoría de entidades, orientado a:

- mejorar mantenibilidad
- separar normalización, clasificación, deduplicación y exportación
- reducir clases genéricas como `Unknown`
- analizar duplicados
- generar artefactos de auditoría por clase y por tipo de problema

## Estructura

- `config.py`: constantes y reglas de ontología
- `normalize.py`: limpieza y canonicalización
- `classify.py`: selección de clase primaria y clases secundarias
- `rules.py`: rescate heurístico de clases genéricas
- `dedupe.py`: detección de duplicados
- `quality.py`: validaciones y checks de completitud
- `metrics.py`: métricas agregadas
- `export.py`: export de JSONs de auditoría
- `cli.py`: entrypoint

## Uso

Desde el directorio padre:

```bash
python -m entity_audit.cli entities.json