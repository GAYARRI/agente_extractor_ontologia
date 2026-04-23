# Iteration Notes - 2026-04-23

## Goal

Improve the tourism ontology pipeline in two directions:

1. Increase recall of tourism entities across a tourism-heavy website.
2. Reduce low-quality candidates, generic captures, and `Unknown` final classes.

## Main Problems Observed

- Too many pages with no extracted entities.
- Too few candidate tourism entities for a site with around 300 tourism-focused pages.
- Frequent collapse to `Unknown`.
- Good entities were missed in listings and editorial pages.
- Bad candidates still leaked through:
  - category labels
  - abstract themes
  - technical fragments
  - contaminated names with narrative tails

## Files Updated

- `src/ontology_utils.py`
- `src/tourism_entity_extractor.py`
- `src/entity_filter.py`
- `src/entity_type_resolver.py`
- `src/tourism_pipeline_ontology_driven.py`
- `src/supervision/llm_supervisor.py`
- `requirements.txt`
- `README.md`
- `_archive/legacy_2026_04_23/README.md`

## Key Changes

### 1. Ontology loading and closed world

- Replaced fragile regex-based ontology parsing with real RDF/XML parsing via `rdflib`.
- Restored a single clean implementation of ontology utilities.
- Improved alias handling toward actual ontology classes.

### 2. Entity extraction

- Expanded lexical coverage for tourism POIs and events.
- Improved extraction from editorial and list-like pages.
- Added cleanup for UI-prefixed strings like:
  - `Ir al contenido`
  - `Reserva tu actividad`
- Improved trailing-noise trimming for contaminated names.
- Reduced duplicate tail captures.

### 3. Entity filtering

- Relaxed overly conservative filtering for valid tourism names.
- Added rejection of:
  - technical fragments
  - category-like fragments
  - theme-like fragments
- Examples now rejected earlier:
  - `Visitas guiadas`
  - `Producción Agraria Ecológica`
  - `Postres Queso Roncal`

### 4. Type resolution

- Strengthened tourism lexical rules and weighted evidence logic.
- Added hard rules for common POIs and events.
- Added hard rejects for pseudo-entities that should not survive to final typing.
- Reduced reliance on generic fallback classes.

### 5. Listing pages and recall

- Removed the hard short-circuit that returned no entities for strict listing pages.
- Increased `top_k` for listing-like pages.
- Added rescue logic for empty pages using strong tourism evidence.
- Added a page-type-aware capture profile:
  - `detail`
  - `listing`
  - `strict_listing`

### 6. Tourism evidence layer

- Connected `TourismEvidenceScore` to the actual pipeline flow.
- Added evidence annotation before ontology matching and later gates.
- Allowed controlled rescue of good tourism candidates with strong evidence.

### 7. LLM supervisor

- Reworked the supervisor so it is instantiated correctly with ontology context.
- Connected `use_fewshots` and external `fewshots` properly.
- Separated the three stages clearly:
  - extraction
  - validation
  - classification
- Normalized few-shot classes against the ontology.
- Prevented generic classes like `Place` from being treated as valid final outputs there.

## Observed Direction of Improvement

- More tourism entities are now being captured from listing/editorial pages.
- Better diversity of classes:
  - `Event`
  - `Route`
  - `TraditionalMarket`
  - `Garden`
  - `Square`
  - `Theater`
- `Unknown` is being pushed toward edge cases rather than common output.

## Remaining Issues

- Some contaminated names still survive in specific classes:
  - `Castle`
  - `Route`
  - `Event`
  - `Monument`
- A few `Unknown` values may still remain after the latest run.
- Some outputs still reflect incomplete enrichment rather than bad extraction.

## Recommended Next Step

Run the pipeline again and review:

1. Remaining `Unknown` entities.
2. False positives inside `Monument`, `Castle`, `Route`, and `Event`.
3. Number of pages still ending with zero entities.
4. Final count of entities vs. previous runs.

## Practical Summary

This iteration focused on opening recall carefully without losing too much precision.

The pipeline is now better at:

- not skipping tourism listing pages
- rescuing valid tourism candidates
- rejecting abstract themes and category fragments
- keeping ontology classification more specific

The next iteration should be mainly about precision cleanup, not major architecture.
