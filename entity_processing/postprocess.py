from typing import Dict, List

from .candidate_filter import should_keep_candidate
from .classify import entity_all_classes, entity_primary_class
from .dedupe import dedupe_entities
from .family_classifier import classify_entity_family
from .name_cleaner import clean_entity_name, extract_raw_name
from .normalize import clean_type, sanitize_types
from .page_classifier import classify_page
from .rules import apply_rescue_rules


def enrich_entity_classification(entity: Dict) -> Dict:
    item = dict(entity)

    raw_name = extract_raw_name(item)
    cleaned_name = clean_entity_name(raw_name)
    item["rawName"] = raw_name
    if cleaned_name:
        item["name"] = cleaned_name

    if "class" in item:
        item["class"] = clean_type(item.get("class"))

    if "types" in item:
        item["types"] = sanitize_types(item.get("types"))

    if "type" in item:
        original_type = item.get("type")
        if isinstance(original_type, (list, tuple)):
            item["type"] = sanitize_types(original_type)
        else:
            cleaned = clean_type(original_type)
            item["type"] = cleaned if cleaned else original_type

    item["pageType"] = classify_page(
        url=item.get("url") or item.get("sourceUrl") or "",
        entity=item,
    )

    item["entityFamily"] = classify_entity_family(item)

    item["allClasses"] = entity_all_classes(item)
    item["primaryClass"] = entity_primary_class(item)

    rescued_class, rescued, reason = apply_rescue_rules(item, item["primaryClass"])
    item["primaryClass"] = rescued_class
    item["classificationRescued"] = rescued

    if rescued:
        item["classificationRescueReason"] = reason

    keep, reason = should_keep_candidate(item, item["pageType"])
    item["postprocessKeep"] = keep
    item["postprocessDecisionReason"] = reason

    return item


def postprocess_entities(entities: List[Dict], enable_dedupe: bool = True) -> List[Dict]:
    enriched = [enrich_entity_classification(entity) for entity in entities]

    # Keep everything for now; only annotate filtering decision
    kept = [entity for entity in enriched if entity.get("postprocessKeep", True)]

    # Fallback: if everything was filtered out, return enriched instead of empty
    if not kept:
        kept = enriched

    if enable_dedupe:
        return dedupe_entities(kept)

    return kept