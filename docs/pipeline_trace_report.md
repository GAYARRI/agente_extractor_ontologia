# Pipeline Trace Report

Trazas de diagnostico por URL.

## https://visitpamplonairuna.com/lugar/archivo-real-y-general-de-navarra

- Entidades finales: `1`

### Entidades

- 'Plaza Consistorial' | class='Square' | type='Square'

### Stderr

```text
[PIPELINE] extract: count=17
[PIPELINE] extract sample_1_type=dict
[PIPELINE] extract sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_2_type=dict
[PIPELINE] extract sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_3_type=dict
[PIPELINE] extract sample_3=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced: count=18
[PIPELINE] extract_coerced sample_1_type=dict
[PIPELINE] extract_coerced sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_2_type=dict
[PIPELINE] extract_coerced sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_3_type=dict
[PIPELINE] extract_coerced sample_3=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean: count=18
[PIPELINE] clean sample_1_type=dict
[PIPELINE] clean sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_2_type=dict
[PIPELINE] clean sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_3_type=dict
[PIPELINE] clean sample_3=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate: count=18
[PIPELINE] deduplicate sample_1_type=dict
[PIPELINE] deduplicate sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_2_type=dict
[PIPELINE] deduplicate sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_3_type=dict
[PIPELINE] deduplicate sample_3=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize: count=18
[PIPELINE] normalize sample_1_type=dict
[PIPELINE] normalize sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize sample_2_type=dict
[PIPELINE] normalize sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize sample_3_type=dict
[PIPELINE] normalize sample_3=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand: count=18
[PIPELINE] expand sample_1_type=dict
[PIPELINE] expand sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand sample_2_type=dict
[PIPELINE] expand sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand sample_3_type=dict
[PIPELINE] expand sample_3=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split: count=18
[PIPELINE] split sample_1_type=dict
[PIPELINE] split sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split sample_2_type=dict
[PIPELINE] split sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split sample_3_type=dict
[PIPELINE] split sample_3=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced: count=18
[PIPELINE] split_coerced sample_1_type=dict
[PIPELINE] split_coerced sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced sample_2_type=dict
[PIPELINE] split_coerced sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced sample_3_type=dict
[PIPELINE] split_coerced sample_3=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter: count=16
[PIPELINE] conservative_filter sample_1_type=dict
[PIPELINE] conservative_filter sample_1=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter sample_2_type=dict
[PIPELINE] conservative_filter sample_2=name='Pamplona Información' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter sample_3_type=dict
[PIPELINE] conservative_filter sample_3=name='Visitas para grupos' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence: count=16
[PIPELINE] tourism_evidence sample_1_type=dict
[PIPELINE] tourism_evidence sample_1=name='Palacio de los Reyes de Navarra' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence sample_2_type=dict
[PIPELINE] tourism_evidence sample_2=name='Pamplona Información' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence sample_3_type=dict
[PIPELINE] tourism_evidence sample_3=name='Visitas para grupos' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates: count=16
[PIPELINE] typed_candidates sample_1_type=dict
[PIPELINE] typed_candidates sample_1=name='Palacio de los Reyes de Navarra' | class='Palace' | type='Palace' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates sample_2_type=dict
[PIPELINE] typed_candidates sample_2=name='Pamplona Información' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates sample_3_type=dict
[PIPELINE] typed_candidates sample_3=name='Visitas para grupos' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match: count=15
[PIPELINE] semantic_match sample_1_type=dict
[PIPELINE] semantic_match sample_1=name='Palacio de los Reyes de Navarra' | class='Palace' | type='Palace' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match sample_2_type=dict
[PIPELINE] semantic_match sample_2=name='Pamplona Información' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match sample_3_type=dict
[PIPELINE] semantic_match sample_3=name='Visitas para grupos' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] rank: count=15
[PIPELINE] rank sample_1_type=dict
[PIPELINE] rank sample_1=name='Palacio Real' | class='Palace' | type='Palace' | semantic_type='' | semantic_score=0.5 | score=6.6 | final_score=6.6
[PIPELINE] rank sample_2_type=dict
[PIPELINE] rank sample_2=name='Palacio de los Reyes de Navarra' | class='Palace' | type='Palace' | semantic_type='' | semantic_score=0.5 | score=5.9 | final_score=5.9
[PIPELINE] rank sample_3_type=dict
[PIPELINE] rank sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] sanitize_ranked: count=12
[PIPELINE] sanitize_ranked sample_1_type=dict
[PIPELINE] sanitize_ranked sample_1=name='Archivo Real y General de Navarra' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.95 | score=3.94 | final_score=3.94
[PIPELINE] sanitize_ranked sample_2_type=dict
[PIPELINE] sanitize_ranked sample_2=name='Archivo Real' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_ranked sample_3_type=dict
[PIPELINE] sanitize_ranked sample_3=name='Palacio Real' | class='Palace' | type='Palace' | semantic_type='' | semantic_score=0.5 | score=6.6 | final_score=6.6
[PIPELINE] llm_supervisor: count=12
[PIPELINE] llm_supervisor sample_1_type=dict
[PIPELINE] llm_supervisor sample_1=name='Archivo Real y General de Navarra' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.95 | score=3.94 | final_score=3.94
[PIPELINE] llm_supervisor sample_2_type=dict
[PIPELINE] llm_supervisor sample_2=name='Archivo Real' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] llm_supervisor sample_3_type=dict
[PIPELINE] llm_supervisor sample_3=name='Palacio Real' | class='Palace' | type='Palace' | semantic_type='' | semantic_score=0.5 | score=6.6 | final_score=6.6
[PIPELINE] sanitize_final: count=12
[PIPELINE] sanitize_final sample_1_type=dict
[PIPELINE] sanitize_final sample_1=name='Archivo Real y General de Navarra' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.95 | score=3.94 | final_score=3.94
[PIPELINE] sanitize_final sample_2_type=dict
[PIPELINE] sanitize_final sample_2=name='Archivo Real' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_final sample_3_type=dict
[PIPELINE] sanitize_final sample_3=name='Palacio Real' | class='Palace' | type='Palace' | semantic_type='' | semantic_score=0.5 | score=6.6 | final_score=6.6
[PIPELINE] cluster: count=12
[PIPELINE] cluster sample_1_type=dict
[PIPELINE] cluster sample_1=name='Archivo Real y General de Navarra' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.95 | score=3.94 | final_score=3.94
[PIPELINE] cluster sample_2_type=dict
[PIPELINE] cluster sample_2=name='Archivo Real' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] cluster sample_3_type=dict
[PIPELINE] cluster sample_3=name='Palacio Real' | class='Palace' | type='Palace' | semantic_type='' | semantic_score=0.5 | score=6.6 | final_score=6.6
[PIPELINE] sanitize_flattened: count=12
[PIPELINE] sanitize_flattened sample_1_type=dict
[PIPELINE] sanitize_flattened sample_1=name='Archivo Real y General de Navarra' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.95 | score=3.94 | final_score=3.94
[PIPELINE] sanitize_flattened sample_2_type=dict
[PIPELINE] sanitize_flattened sample_2=name='Archivo Real' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_flattened sample_3_type=dict
[PIPELINE] sanitize_flattened sample_3=name='Palacio Real' | class='Palace' | type='Palace' | semantic_type='' | semantic_score=0.5 | score=6.6 | final_score=6.6
[PIPELINE] enriched_final: count=12
[PIPELINE] enriched_final sample_1_type=dict
[PIPELINE] enriched_final sample_1=name='Archivo Real y General de Navarra' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.95 | score=3.94 | final_score=3.94
[PIPELINE] enriched_final sample_2_type=dict
[PIPELINE] enriched_final sample_2=name='Archivo Real' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] enriched_final sample_3_type=dict
[PIPELINE] enriched_final sample_3=name='Palacio Real' | class='Palace' | type='Palace' | semantic_type='' | semantic_score=0.5 | score=6.6 | final_score=6.6
[PIPELINE] final_filter kept=10 rejected=2
[PIPELINE] final_filter rejected_1=name='Archivo Real y General de Navarra' reasons=['phrase_fragment']
[PIPELINE] final_filter rejected_2=name='Palacio de los Reyes de Navarra' reasons=['phrase_fragment']
[PIPELINE] final_filter: count=10
[PIPELINE] final_filter sample_1_type=dict
[PIPELINE] final_filter sample_1=name='Archivo Real' | class='HistoricalOrCulturalResource' | type='HistoricalOrCulturalResource' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] final_filter sample_2_type=dict
[PIPELINE] final_filter sample_2=name='Palacio Real' | class='Palace' | type='Palace' | semantic_type='' | semantic_score=0.5 | score=6.6 | final_score=6.6
[PIPELINE] final_filter sample_3_type=dict
[PIPELINE] final_filter sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] postprocessed_final: count=1
[PIPELINE] postprocessed_final sample_1_type=dict
[PIPELINE] postprocessed_final sample_1=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] closed_world: count=1
[PIPELINE] closed_world sample_1_type=dict
[PIPELINE] closed_world sample_1=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
```

## https://visitpamplonairuna.com/lugar/catedral-de-santa-maria-la-real

- Entidades finales: `1`

### Entidades

- 'Catedral de Pamplona' | class='Cathedral' | type='Cathedral'

### Stderr

```text
[PIPELINE] extract: count=23
[PIPELINE] extract sample_1_type=dict
[PIPELINE] extract sample_1=name='Catedral de Santa María la Real Construida en' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_2_type=dict
[PIPELINE] extract sample_2=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_3_type=dict
[PIPELINE] extract sample_3=name='Ayuntamiento de Pamplona Preguntas' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced: count=24
[PIPELINE] extract_coerced sample_1_type=dict
[PIPELINE] extract_coerced sample_1=name='Catedral de Santa María la Real Construida en' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_2_type=dict
[PIPELINE] extract_coerced sample_2=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_3_type=dict
[PIPELINE] extract_coerced sample_3=name='Ayuntamiento de Pamplona Preguntas' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean: count=24
[PIPELINE] clean sample_1_type=dict
[PIPELINE] clean sample_1=name='Catedral de Santa María la Real Construida en' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_2_type=dict
[PIPELINE] clean sample_2=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_3_type=dict
[PIPELINE] clean sample_3=name='Ayuntamiento de Pamplona Preguntas' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate: count=24
[PIPELINE] deduplicate sample_1_type=dict
[PIPELINE] deduplicate sample_1=name='Catedral de Santa María la Real Construida en' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_2_type=dict
[PIPELINE] deduplicate sample_2=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_3_type=dict
[PIPELINE] deduplicate sample_3=name='Ayuntamiento de Pamplona Preguntas' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize: count=22
[PIPELINE] normalize sample_1_type=dict
[PIPELINE] normalize sample_1=name='Catedral de Santa María la Real' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] normalize sample_2_type=dict
[PIPELINE] normalize sample_2=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize sample_3_type=dict
[PIPELINE] normalize sample_3=name='Ayuntamiento de Pamplona Preguntas' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand: count=22
[PIPELINE] expand sample_1_type=dict
[PIPELINE] expand sample_1=name='Catedral de Santa María la Real' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] expand sample_2_type=dict
[PIPELINE] expand sample_2=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand sample_3_type=dict
[PIPELINE] expand sample_3=name='Ayuntamiento de Pamplona Preguntas' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split: count=22
[PIPELINE] split sample_1_type=dict
[PIPELINE] split sample_1=name='Catedral de Santa María la Real' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] split sample_2_type=dict
[PIPELINE] split sample_2=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split sample_3_type=dict
[PIPELINE] split sample_3=name='Ayuntamiento de Pamplona Preguntas' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced: count=22
[PIPELINE] split_coerced sample_1_type=dict
[PIPELINE] split_coerced sample_1=name='Catedral de Santa María la Real' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] split_coerced sample_2_type=dict
[PIPELINE] split_coerced sample_2=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced sample_3_type=dict
[PIPELINE] split_coerced sample_3=name='Ayuntamiento de Pamplona Preguntas' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter: count=19
[PIPELINE] conservative_filter sample_1_type=dict
[PIPELINE] conservative_filter sample_1=name='Catedral de Santa María la Real' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] conservative_filter sample_2_type=dict
[PIPELINE] conservative_filter sample_2=name='Museo de la Catedral' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter sample_3_type=dict
[PIPELINE] conservative_filter sample_3=name='Catedral de Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence: count=16
[PIPELINE] tourism_evidence sample_1_type=dict
[PIPELINE] tourism_evidence sample_1=name='Catedral de Santa María la Real' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] tourism_evidence sample_2_type=dict
[PIPELINE] tourism_evidence sample_2=name='Museo de la Catedral' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence sample_3_type=dict
[PIPELINE] tourism_evidence sample_3=name='Catedral de Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates: count=16
[PIPELINE] typed_candidates sample_1_type=dict
[PIPELINE] typed_candidates sample_1=name='Catedral de Santa María la Real' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] typed_candidates sample_2_type=dict
[PIPELINE] typed_candidates sample_2=name='Museo de la Catedral' | class='Museum' | type='Museum' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates sample_3_type=dict
[PIPELINE] typed_candidates sample_3=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match: count=16
[PIPELINE] semantic_match sample_1_type=dict
[PIPELINE] semantic_match sample_1=name='Catedral de Santa María la Real' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] semantic_match sample_2_type=dict
[PIPELINE] semantic_match sample_2=name='Museo de la Catedral' | class='Museum' | type='Museum' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match sample_3_type=dict
[PIPELINE] semantic_match sample_3=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] rank: count=16
[PIPELINE] rank sample_1_type=dict
[PIPELINE] rank sample_1=name='Museo de la Catedral' | class='Museum' | type='Museum' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] rank sample_2_type=dict
[PIPELINE] rank sample_2=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] rank sample_3_type=dict
[PIPELINE] rank sample_3=name='Catedral de Santa María la Real' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.95 | score=6.44 | final_score=6.44
[PIPELINE] sanitize_ranked: count=12
[PIPELINE] sanitize_ranked sample_1_type=dict
[PIPELINE] sanitize_ranked sample_1=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] sanitize_ranked sample_2_type=dict
[PIPELINE] sanitize_ranked sample_2=name='España Catedral' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=5.6 | final_score=5.6
[PIPELINE] sanitize_ranked sample_3_type=dict
[PIPELINE] sanitize_ranked sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.35 | final_score=5.35
[PIPELINE] llm_supervisor: count=12
[PIPELINE] llm_supervisor sample_1_type=dict
[PIPELINE] llm_supervisor sample_1=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] llm_supervisor sample_2_type=dict
[PIPELINE] llm_supervisor sample_2=name='España Catedral' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=5.6 | final_score=5.6
[PIPELINE] llm_supervisor sample_3_type=dict
[PIPELINE] llm_supervisor sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.35 | final_score=5.35
[PIPELINE] sanitize_final: count=12
[PIPELINE] sanitize_final sample_1_type=dict
[PIPELINE] sanitize_final sample_1=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] sanitize_final sample_2_type=dict
[PIPELINE] sanitize_final sample_2=name='España Catedral' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=5.6 | final_score=5.6
[PIPELINE] sanitize_final sample_3_type=dict
[PIPELINE] sanitize_final sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.35 | final_score=5.35
[PIPELINE] cluster: count=12
[PIPELINE] cluster sample_1_type=dict
[PIPELINE] cluster sample_1=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] cluster sample_2_type=dict
[PIPELINE] cluster sample_2=name='España Catedral' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=5.6 | final_score=5.6
[PIPELINE] cluster sample_3_type=dict
[PIPELINE] cluster sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.35 | final_score=5.35
[PIPELINE] sanitize_flattened: count=12
[PIPELINE] sanitize_flattened sample_1_type=dict
[PIPELINE] sanitize_flattened sample_1=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] sanitize_flattened sample_2_type=dict
[PIPELINE] sanitize_flattened sample_2=name='España Catedral' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=5.6 | final_score=5.6
[PIPELINE] sanitize_flattened sample_3_type=dict
[PIPELINE] sanitize_flattened sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.35 | final_score=5.35
[PIPELINE] enriched_final: count=12
[PIPELINE] enriched_final sample_1_type=dict
[PIPELINE] enriched_final sample_1=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] enriched_final sample_2_type=dict
[PIPELINE] enriched_final sample_2=name='España Catedral' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=5.6 | final_score=5.6
[PIPELINE] enriched_final sample_3_type=dict
[PIPELINE] enriched_final sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.35 | final_score=5.35
[PIPELINE] final_filter kept=12 rejected=0
[PIPELINE] final_filter: count=12
[PIPELINE] final_filter sample_1_type=dict
[PIPELINE] final_filter sample_1=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] final_filter sample_2_type=dict
[PIPELINE] final_filter sample_2=name='España Catedral' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=5.6 | final_score=5.6
[PIPELINE] final_filter sample_3_type=dict
[PIPELINE] final_filter sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.35 | final_score=5.35
[PIPELINE] postprocessed_final: count=1
[PIPELINE] postprocessed_final sample_1_type=dict
[PIPELINE] postprocessed_final sample_1=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
[PIPELINE] closed_world: count=1
[PIPELINE] closed_world sample_1_type=dict
[PIPELINE] closed_world sample_1=name='Catedral de Pamplona' | class='Cathedral' | type='Cathedral' | semantic_type='' | semantic_score=0.5 | score=6.9 | final_score=6.9
```

## https://visitpamplonairuna.com/lugar/espacio-sanfermin-espazioa

- Entidades finales: `1`

### Entidades

- 'Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument'

### Stderr

```text
[PIPELINE] extract: count=11
[PIPELINE] extract sample_1_type=dict
[PIPELINE] extract sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_2_type=dict
[PIPELINE] extract sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_3_type=dict
[PIPELINE] extract sample_3=name='Marco Topo Recomendado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced: count=12
[PIPELINE] extract_coerced sample_1_type=dict
[PIPELINE] extract_coerced sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_2_type=dict
[PIPELINE] extract_coerced sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_3_type=dict
[PIPELINE] extract_coerced sample_3=name='Marco Topo Recomendado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean: count=12
[PIPELINE] clean sample_1_type=dict
[PIPELINE] clean sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_2_type=dict
[PIPELINE] clean sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_3_type=dict
[PIPELINE] clean sample_3=name='Marco Topo Recomendado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate: count=12
[PIPELINE] deduplicate sample_1_type=dict
[PIPELINE] deduplicate sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_2_type=dict
[PIPELINE] deduplicate sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_3_type=dict
[PIPELINE] deduplicate sample_3=name='Marco Topo Recomendado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize: count=12
[PIPELINE] normalize sample_1_type=dict
[PIPELINE] normalize sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize sample_2_type=dict
[PIPELINE] normalize sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize sample_3_type=dict
[PIPELINE] normalize sample_3=name='Marco Topo Recomendado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand: count=12
[PIPELINE] expand sample_1_type=dict
[PIPELINE] expand sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand sample_2_type=dict
[PIPELINE] expand sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand sample_3_type=dict
[PIPELINE] expand sample_3=name='Marco Topo Recomendado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split: count=12
[PIPELINE] split sample_1_type=dict
[PIPELINE] split sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split sample_2_type=dict
[PIPELINE] split sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split sample_3_type=dict
[PIPELINE] split sample_3=name='Marco Topo Recomendado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced: count=12
[PIPELINE] split_coerced sample_1_type=dict
[PIPELINE] split_coerced sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced sample_2_type=dict
[PIPELINE] split_coerced sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced sample_3_type=dict
[PIPELINE] split_coerced sample_3=name='Marco Topo Recomendado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter: count=10
[PIPELINE] conservative_filter sample_1_type=dict
[PIPELINE] conservative_filter sample_1=name='Marco Topo' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter sample_2_type=dict
[PIPELINE] conservative_filter sample_2=name='Marco Topo Información' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter sample_3_type=dict
[PIPELINE] conservative_filter sample_3=name='Plaza Consistorial' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence: count=11
[PIPELINE] tourism_evidence sample_1_type=dict
[PIPELINE] tourism_evidence sample_1=name='Marco Topo' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence sample_2_type=dict
[PIPELINE] tourism_evidence sample_2=name='Marco Topo Información' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence sample_3_type=dict
[PIPELINE] tourism_evidence sample_3=name='Plaza Consistorial' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates: count=11
[PIPELINE] typed_candidates sample_1_type=dict
[PIPELINE] typed_candidates sample_1=name='Marco Topo' | class='Monument' | type='Monument' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates sample_2_type=dict
[PIPELINE] typed_candidates sample_2=name='Marco Topo Información' | class='Monument' | type='Monument' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates sample_3_type=dict
[PIPELINE] typed_candidates sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match: count=11
[PIPELINE] semantic_match sample_1_type=dict
[PIPELINE] semantic_match sample_1=name='Marco Topo' | class='Monument' | type='Monument' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match sample_2_type=dict
[PIPELINE] semantic_match sample_2=name='Marco Topo Información' | class='Monument' | type='Monument' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match sample_3_type=dict
[PIPELINE] semantic_match sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] rank: count=11
[PIPELINE] rank sample_1_type=dict
[PIPELINE] rank sample_1=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] rank sample_2_type=dict
[PIPELINE] rank sample_2=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
[PIPELINE] rank sample_3_type=dict
[PIPELINE] rank sample_3=name='Marco Topo' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_ranked: count=11
[PIPELINE] sanitize_ranked sample_1_type=dict
[PIPELINE] sanitize_ranked sample_1=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
[PIPELINE] sanitize_ranked sample_2_type=dict
[PIPELINE] sanitize_ranked sample_2=name='Espacio SanfermIN' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_ranked sample_3_type=dict
[PIPELINE] sanitize_ranked sample_3=name='San Fermín' | class='Event' | type='Event' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] llm_supervisor: count=11
[PIPELINE] llm_supervisor sample_1_type=dict
[PIPELINE] llm_supervisor sample_1=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
[PIPELINE] llm_supervisor sample_2_type=dict
[PIPELINE] llm_supervisor sample_2=name='Espacio SanfermIN' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] llm_supervisor sample_3_type=dict
[PIPELINE] llm_supervisor sample_3=name='San Fermín' | class='Event' | type='Event' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_final: count=11
[PIPELINE] sanitize_final sample_1_type=dict
[PIPELINE] sanitize_final sample_1=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
[PIPELINE] sanitize_final sample_2_type=dict
[PIPELINE] sanitize_final sample_2=name='Espacio SanfermIN' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_final sample_3_type=dict
[PIPELINE] sanitize_final sample_3=name='San Fermín' | class='Event' | type='Event' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] cluster: count=11
[PIPELINE] cluster sample_1_type=dict
[PIPELINE] cluster sample_1=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
[PIPELINE] cluster sample_2_type=dict
[PIPELINE] cluster sample_2=name='Espacio SanfermIN' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] cluster sample_3_type=dict
[PIPELINE] cluster sample_3=name='San Fermín' | class='Event' | type='Event' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_flattened: count=11
[PIPELINE] sanitize_flattened sample_1_type=dict
[PIPELINE] sanitize_flattened sample_1=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
[PIPELINE] sanitize_flattened sample_2_type=dict
[PIPELINE] sanitize_flattened sample_2=name='Espacio SanfermIN' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_flattened sample_3_type=dict
[PIPELINE] sanitize_flattened sample_3=name='San Fermín' | class='Event' | type='Event' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] enriched_final: count=11
[PIPELINE] enriched_final sample_1_type=dict
[PIPELINE] enriched_final sample_1=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
[PIPELINE] enriched_final sample_2_type=dict
[PIPELINE] enriched_final sample_2=name='Espacio SanfermIN' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] enriched_final sample_3_type=dict
[PIPELINE] enriched_final sample_3=name='San Fermín' | class='Event' | type='Event' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] final_filter kept=9 rejected=2
[PIPELINE] final_filter rejected_1=name='El Camino' reasons=['weak_route_name']
[PIPELINE] final_filter rejected_2=name='Camino de Santiago Descubre Pamplona' reasons=['foreign_noise']
[PIPELINE] final_filter: count=9
[PIPELINE] final_filter sample_1_type=dict
[PIPELINE] final_filter sample_1=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
[PIPELINE] final_filter sample_2_type=dict
[PIPELINE] final_filter sample_2=name='Espacio SanfermIN' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] final_filter sample_3_type=dict
[PIPELINE] final_filter sample_3=name='San Fermín' | class='Event' | type='Event' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] postprocessed_final: count=1
[PIPELINE] postprocessed_final sample_1_type=dict
[PIPELINE] postprocessed_final sample_1=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
[PIPELINE] closed_world: count=1
[PIPELINE] closed_world sample_1_type=dict
[PIPELINE] closed_world sample_1=name='Espacio SanfermIN! Espazioa' | class='Monument' | type='Monument' | semantic_type='' | semantic_score=0.95 | score=4.89 | final_score=4.89
```

## https://visitpamplonairuna.com/en/lugar/belena-de-portalapea

- Entidades finales: `1`

### Entidades

- 'Plaza Consistorial' | class='Square' | type='Square'

### Stderr

```text
[PIPELINE] extract: count=9
[PIPELINE] extract sample_1_type=dict
[PIPELINE] extract sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_2_type=dict
[PIPELINE] extract sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_3_type=dict
[PIPELINE] extract sample_3=name='Portalapea La Belena' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced: count=10
[PIPELINE] extract_coerced sample_1_type=dict
[PIPELINE] extract_coerced sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_2_type=dict
[PIPELINE] extract_coerced sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_3_type=dict
[PIPELINE] extract_coerced sample_3=name='Portalapea La Belena' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean: count=10
[PIPELINE] clean sample_1_type=dict
[PIPELINE] clean sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_2_type=dict
[PIPELINE] clean sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_3_type=dict
[PIPELINE] clean sample_3=name='Portalapea La Belena' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate: count=10
[PIPELINE] deduplicate sample_1_type=dict
[PIPELINE] deduplicate sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_2_type=dict
[PIPELINE] deduplicate sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_3_type=dict
[PIPELINE] deduplicate sample_3=name='Portalapea La Belena' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize: count=9
[PIPELINE] normalize sample_1_type=dict
[PIPELINE] normalize sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize sample_2_type=dict
[PIPELINE] normalize sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize sample_3_type=dict
[PIPELINE] normalize sample_3=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] expand: count=9
[PIPELINE] expand sample_1_type=dict
[PIPELINE] expand sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand sample_2_type=dict
[PIPELINE] expand sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand sample_3_type=dict
[PIPELINE] expand sample_3=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] split: count=9
[PIPELINE] split sample_1_type=dict
[PIPELINE] split sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split sample_2_type=dict
[PIPELINE] split sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split sample_3_type=dict
[PIPELINE] split sample_3=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] split_coerced: count=9
[PIPELINE] split_coerced sample_1_type=dict
[PIPELINE] split_coerced sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced sample_2_type=dict
[PIPELINE] split_coerced sample_2=name='Ayuntamiento de Pamplona Reserva' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced sample_3_type=dict
[PIPELINE] split_coerced sample_3=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] conservative_filter: count=7
[PIPELINE] conservative_filter sample_1_type=dict
[PIPELINE] conservative_filter sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] conservative_filter sample_2_type=dict
[PIPELINE] conservative_filter sample_2=name='Plaza Consistorial' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter sample_3_type=dict
[PIPELINE] conservative_filter sample_3=name='Pamplona Planifica' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence: count=8
[PIPELINE] tourism_evidence sample_1_type=dict
[PIPELINE] tourism_evidence sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] tourism_evidence sample_2_type=dict
[PIPELINE] tourism_evidence sample_2=name='Plaza Consistorial' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence sample_3_type=dict
[PIPELINE] tourism_evidence sample_3=name='Pamplona Planifica' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates: count=8
[PIPELINE] typed_candidates sample_1_type=dict
[PIPELINE] typed_candidates sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] typed_candidates sample_2_type=dict
[PIPELINE] typed_candidates sample_2=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates sample_3_type=dict
[PIPELINE] typed_candidates sample_3=name='Pamplona Planifica' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match: count=8
[PIPELINE] semantic_match sample_1_type=dict
[PIPELINE] semantic_match sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] semantic_match sample_2_type=dict
[PIPELINE] semantic_match sample_2=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match sample_3_type=dict
[PIPELINE] semantic_match sample_3=name='Pamplona Planifica' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] rank: count=8
[PIPELINE] rank sample_1_type=dict
[PIPELINE] rank sample_1=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] rank sample_2_type=dict
[PIPELINE] rank sample_2=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.95 | score=4.94 | final_score=4.94
[PIPELINE] rank sample_3_type=dict
[PIPELINE] rank sample_3=name='San Saturnino' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_ranked: count=8
[PIPELINE] sanitize_ranked sample_1_type=dict
[PIPELINE] sanitize_ranked sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.95 | score=4.94 | final_score=4.94
[PIPELINE] sanitize_ranked sample_2_type=dict
[PIPELINE] sanitize_ranked sample_2=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] sanitize_ranked sample_3_type=dict
[PIPELINE] sanitize_ranked sample_3=name='San Saturnino' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] llm_supervisor: count=8
[PIPELINE] llm_supervisor sample_1_type=dict
[PIPELINE] llm_supervisor sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.95 | score=4.94 | final_score=4.94
[PIPELINE] llm_supervisor sample_2_type=dict
[PIPELINE] llm_supervisor sample_2=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] llm_supervisor sample_3_type=dict
[PIPELINE] llm_supervisor sample_3=name='San Saturnino' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_final: count=8
[PIPELINE] sanitize_final sample_1_type=dict
[PIPELINE] sanitize_final sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.95 | score=4.94 | final_score=4.94
[PIPELINE] sanitize_final sample_2_type=dict
[PIPELINE] sanitize_final sample_2=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] sanitize_final sample_3_type=dict
[PIPELINE] sanitize_final sample_3=name='San Saturnino' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] cluster: count=8
[PIPELINE] cluster sample_1_type=dict
[PIPELINE] cluster sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.95 | score=4.94 | final_score=4.94
[PIPELINE] cluster sample_2_type=dict
[PIPELINE] cluster sample_2=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] cluster sample_3_type=dict
[PIPELINE] cluster sample_3=name='San Saturnino' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] sanitize_flattened: count=8
[PIPELINE] sanitize_flattened sample_1_type=dict
[PIPELINE] sanitize_flattened sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.95 | score=4.94 | final_score=4.94
[PIPELINE] sanitize_flattened sample_2_type=dict
[PIPELINE] sanitize_flattened sample_2=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] sanitize_flattened sample_3_type=dict
[PIPELINE] sanitize_flattened sample_3=name='San Saturnino' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] enriched_final: count=8
[PIPELINE] enriched_final sample_1_type=dict
[PIPELINE] enriched_final sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.95 | score=4.94 | final_score=4.94
[PIPELINE] enriched_final sample_2_type=dict
[PIPELINE] enriched_final sample_2=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] enriched_final sample_3_type=dict
[PIPELINE] enriched_final sample_3=name='San Saturnino' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.5 | score=4.1 | final_score=4.1
[PIPELINE] final_filter kept=2 rejected=6
[PIPELINE] final_filter rejected_1=name='San Saturnino' reasons=['weak_type_and_bad_name']
[PIPELINE] final_filter rejected_2=name='Marco Topo' reasons=['weak_type_and_bad_name']
[PIPELINE] final_filter rejected_3=name='San Cernin Tres' reasons=['weak_type_and_bad_name']
[PIPELINE] final_filter rejected_4=name='Pamplona Planifica' reasons=['weak_type_and_bad_name']
[PIPELINE] final_filter rejected_5=name='El Camino' reasons=['weak_route_name']
[PIPELINE] final_filter: count=2
[PIPELINE] final_filter sample_1_type=dict
[PIPELINE] final_filter sample_1=name='Belena de Portalapea' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score=0.95 | score=4.94 | final_score=4.94
[PIPELINE] final_filter sample_2_type=dict
[PIPELINE] final_filter sample_2=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] postprocessed_final: count=1
[PIPELINE] postprocessed_final sample_1_type=dict
[PIPELINE] postprocessed_final sample_1=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] closed_world: count=1
[PIPELINE] closed_world sample_1_type=dict
[PIPELINE] closed_world sample_1=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
```

## https://visitpamplonairuna.com/en/lugar/pump-track

- Entidades finales: `1`

### Entidades

- 'Pump Track Pamplona' | class='' | type=None

### Stderr

```text
[PIPELINE] extract: count=6
[PIPELINE] extract sample_1_type=dict
[PIPELINE] extract sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_2_type=dict
[PIPELINE] extract sample_2=name='Ayuntamiento de Pamplona Pump Track' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract sample_3_type=dict
[PIPELINE] extract sample_3=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced: count=7
[PIPELINE] extract_coerced sample_1_type=dict
[PIPELINE] extract_coerced sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_2_type=dict
[PIPELINE] extract_coerced sample_2=name='Ayuntamiento de Pamplona Pump Track' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] extract_coerced sample_3_type=dict
[PIPELINE] extract_coerced sample_3=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean: count=7
[PIPELINE] clean sample_1_type=dict
[PIPELINE] clean sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_2_type=dict
[PIPELINE] clean sample_2=name='Ayuntamiento de Pamplona Pump Track' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] clean sample_3_type=dict
[PIPELINE] clean sample_3=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate: count=7
[PIPELINE] deduplicate sample_1_type=dict
[PIPELINE] deduplicate sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_2_type=dict
[PIPELINE] deduplicate sample_2=name='Ayuntamiento de Pamplona Pump Track' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] deduplicate sample_3_type=dict
[PIPELINE] deduplicate sample_3=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize: count=6
[PIPELINE] normalize sample_1_type=dict
[PIPELINE] normalize sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] normalize sample_2_type=dict
[PIPELINE] normalize sample_2=name='Pump Track Pamplona' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] normalize sample_3_type=dict
[PIPELINE] normalize sample_3=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand: count=6
[PIPELINE] expand sample_1_type=dict
[PIPELINE] expand sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] expand sample_2_type=dict
[PIPELINE] expand sample_2=name='Pump Track Pamplona' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] expand sample_3_type=dict
[PIPELINE] expand sample_3=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split: count=6
[PIPELINE] split sample_1_type=dict
[PIPELINE] split sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split sample_2_type=dict
[PIPELINE] split sample_2=name='Pump Track Pamplona' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] split sample_3_type=dict
[PIPELINE] split sample_3=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced: count=6
[PIPELINE] split_coerced sample_1_type=dict
[PIPELINE] split_coerced sample_1=name='Camino de Santiago Descubre Pamplona' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] split_coerced sample_2_type=dict
[PIPELINE] split_coerced sample_2=name='Pump Track Pamplona' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] split_coerced sample_3_type=dict
[PIPELINE] split_coerced sample_3=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter: count=5
[PIPELINE] conservative_filter sample_1_type=dict
[PIPELINE] conservative_filter sample_1=name='Pump Track Pamplona' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] conservative_filter sample_2_type=dict
[PIPELINE] conservative_filter sample_2=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] conservative_filter sample_3_type=dict
[PIPELINE] conservative_filter sample_3=name='Plaza Consistorial' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence: count=6
[PIPELINE] tourism_evidence sample_1_type=dict
[PIPELINE] tourism_evidence sample_1=name='Pump Track Pamplona' | class='Unknown' | type='Unknown' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] tourism_evidence sample_2_type=dict
[PIPELINE] tourism_evidence sample_2=name='Pump Track Ubicado' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] tourism_evidence sample_3_type=dict
[PIPELINE] tourism_evidence sample_3=name='Plaza Consistorial' | class='Thing' | type='Thing' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates: count=6
[PIPELINE] typed_candidates sample_1_type=dict
[PIPELINE] typed_candidates sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] typed_candidates sample_2_type=dict
[PIPELINE] typed_candidates sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] typed_candidates sample_3_type=dict
[PIPELINE] typed_candidates sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match: count=6
[PIPELINE] semantic_match sample_1_type=dict
[PIPELINE] semantic_match sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score='' | score=0.95 | final_score=''
[PIPELINE] semantic_match sample_2_type=dict
[PIPELINE] semantic_match sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] semantic_match sample_3_type=dict
[PIPELINE] semantic_match sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score='' | score=0.5 | final_score=''
[PIPELINE] rank: count=6
[PIPELINE] rank sample_1_type=dict
[PIPELINE] rank sample_1=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] rank sample_2_type=dict
[PIPELINE] rank sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.5 | score=4.35 | final_score=4.35
[PIPELINE] rank sample_3_type=dict
[PIPELINE] rank sample_3=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
[PIPELINE] sanitize_ranked: count=6
[PIPELINE] sanitize_ranked sample_1_type=dict
[PIPELINE] sanitize_ranked sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
[PIPELINE] sanitize_ranked sample_2_type=dict
[PIPELINE] sanitize_ranked sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.5 | score=4.35 | final_score=4.35
[PIPELINE] sanitize_ranked sample_3_type=dict
[PIPELINE] sanitize_ranked sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] llm_supervisor: count=6
[PIPELINE] llm_supervisor sample_1_type=dict
[PIPELINE] llm_supervisor sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
[PIPELINE] llm_supervisor sample_2_type=dict
[PIPELINE] llm_supervisor sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.5 | score=4.35 | final_score=4.35
[PIPELINE] llm_supervisor sample_3_type=dict
[PIPELINE] llm_supervisor sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] sanitize_final: count=6
[PIPELINE] sanitize_final sample_1_type=dict
[PIPELINE] sanitize_final sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
[PIPELINE] sanitize_final sample_2_type=dict
[PIPELINE] sanitize_final sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.5 | score=4.35 | final_score=4.35
[PIPELINE] sanitize_final sample_3_type=dict
[PIPELINE] sanitize_final sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] cluster: count=6
[PIPELINE] cluster sample_1_type=dict
[PIPELINE] cluster sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
[PIPELINE] cluster sample_2_type=dict
[PIPELINE] cluster sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.5 | score=4.35 | final_score=4.35
[PIPELINE] cluster sample_3_type=dict
[PIPELINE] cluster sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] sanitize_flattened: count=6
[PIPELINE] sanitize_flattened sample_1_type=dict
[PIPELINE] sanitize_flattened sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
[PIPELINE] sanitize_flattened sample_2_type=dict
[PIPELINE] sanitize_flattened sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.5 | score=4.35 | final_score=4.35
[PIPELINE] sanitize_flattened sample_3_type=dict
[PIPELINE] sanitize_flattened sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] enriched_final: count=6
[PIPELINE] enriched_final sample_1_type=dict
[PIPELINE] enriched_final sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
[PIPELINE] enriched_final sample_2_type=dict
[PIPELINE] enriched_final sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.5 | score=4.35 | final_score=4.35
[PIPELINE] enriched_final sample_3_type=dict
[PIPELINE] enriched_final sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] final_filter kept=4 rejected=2
[PIPELINE] final_filter rejected_1=name='El Camino' reasons=['weak_route_name']
[PIPELINE] final_filter rejected_2=name='Camino de Santiago Descubre Pamplona' reasons=['foreign_noise']
[PIPELINE] final_filter: count=4
[PIPELINE] final_filter sample_1_type=dict
[PIPELINE] final_filter sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
[PIPELINE] final_filter sample_2_type=dict
[PIPELINE] final_filter sample_2=name='Pump Track Ubicado' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.5 | score=4.35 | final_score=4.35
[PIPELINE] final_filter sample_3_type=dict
[PIPELINE] final_filter sample_3=name='Plaza Consistorial' | class='Square' | type='Square' | semantic_type='' | semantic_score=0.5 | score=5.1 | final_score=5.1
[PIPELINE] postprocessed_final: count=1
[PIPELINE] postprocessed_final sample_1_type=dict
[PIPELINE] postprocessed_final sample_1=name='Pump Track Pamplona' | class='SportsCenter' | type='SportsCenter' | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
[PIPELINE] closed_world: count=1
[PIPELINE] closed_world sample_1_type=dict
[PIPELINE] closed_world sample_1=name='Pump Track Pamplona' | class='' | type=None | semantic_type='' | semantic_score=0.95 | score=3.89 | final_score=3.89
```
