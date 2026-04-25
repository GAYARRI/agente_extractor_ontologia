# Borrador de Muestra para Iteracion

Este borrador se ha generado automaticamente a partir de `entities.json` y `entities_page_counts.json`.
Completa manualmente las columnas `Esperado` y ajusta `Tipo de error` si hace falta.

| ID | URL | Familia de pagina | Esperado | Actual | Tipo de error | Notas |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | https://visitpamplonairuna.com/ | detalle |  | 0 entidades | falso negativo potencial | Revisar si la pagina deberia producir entidades o ignorarse. |
| 2 | https://visitpamplonairuna.com/?elementor_library=privilegio-de-la-union | detalle |  | 0 entidades | falso negativo potencial | Revisar si la pagina deberia producir entidades o ignorarse. |
| 3 | https://visitpamplonairuna.com/area-profesional/estrategias-y-planes-municipales | institucional |  | 0 entidades | falso negativo potencial | Revisar si la pagina deberia producir entidades o ignorarse. |
| 4 | https://visitpamplonairuna.com/area-profesional/estudios-e-informes | institucional |  | 0 entidades | falso negativo potencial | Revisar si la pagina deberia producir entidades o ignorarse. |
| 5 | https://visitpamplonairuna.com/area-profesional/licitaciones | institucional |  | 0 entidades | falso negativo potencial | Revisar si la pagina deberia producir entidades o ignorarse. |
| 6 | https://visitpamplonairuna.com/area-profesional | institucional |  | 1 entidades | clases: Location | mal clasificado potencial | La pagina tiene tipos genericos o de baja señal. |
| 7 | https://visitpamplonairuna.com/aviso-legal | detalle |  | 1 entidades | clases: Location | mal clasificado potencial | La pagina tiene tipos genericos o de baja señal. |
| 8 | https://visitpamplonairuna.com/en/lugar/archivo-real-y-general-de-navarra | detalle |  | 1 entidades | clases: Location | mal clasificado potencial | La pagina tiene tipos genericos o de baja señal. |
| 9 | https://visitpamplonairuna.com/en/lugar/pump-track | detalle |  | 1 entidades | clases: Location | mal clasificado potencial | La pagina tiene tipos genericos o de baja señal. |
| 10 | https://visitpamplonairuna.com/en/lugar/skate-park-antoniutti | detalle |  | 1 entidades | clases: Location | mal clasificado potencial | La pagina tiene tipos genericos o de baja señal. |
| 11 | https://visitpamplonairuna.com/area-profesional/noticias-pstd-sf365 | institucional |  | 1 entidades | clases: TownHall | caso institucional a validar | Comprobar si deberia producir PublicService, TourismOrganisation, Promotion, etc. |
| 12 | https://visitpamplonairuna.com/ayuntamiento/en-familia | institucional |  | 1 entidades | clases: Event | caso institucional a validar | Comprobar si deberia producir PublicService, TourismOrganisation, Promotion, etc. |
| 13 | https://visitpamplonairuna.com/en/lugar/ayuntamiento | institucional |  | 1 entidades | clases: TownHall | caso institucional a validar | Comprobar si deberia producir PublicService, TourismOrganisation, Promotion, etc. |
| 14 | https://visitpamplonairuna.com/plan-de-sostenibilidad-turistica | institucional |  | 1 entidades | clases: Location | caso institucional a validar | Comprobar si deberia producir PublicService, TourismOrganisation, Promotion, etc. |
