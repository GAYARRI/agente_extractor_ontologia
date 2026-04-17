from collections import Counter, defaultdict
from typing import Any, Dict, List

from ..entity_processing.classify import class_quality, entity_all_classes, entity_primary_class, entity_specific_classes
from ..entity_processing.dedupe import dedupe_stats, duplicate_groups_only, group_duplicates
from .quality import has_class_conflict, has_coordinates, has_image, entity_missing_expected_fields
from ..entity_processing.rules import apply_rescue_rules


def compute_audit(data: List[Dict[str, Any]], multi_class: bool = False) -> Dict[str, Any]:
    total = len(data)
    total_with_image = sum(1 for e in data if has_image(e))
    total_with_coordinates = sum(1 for e in data if has_coordinates(e))

    groups = group_duplicates(data)
    dup_groups = duplicate_groups_only(groups)
    dup_stats = dedupe_stats(groups)

    primary_quality_counter = Counter()
    conflict_count = 0
    ambiguous_count = 0
    rescued_count = 0
    low_completeness_count = 0
    ambiguous_pair_counter = Counter()

    stats_by_class = defaultdict(lambda: {
        "total": 0,
        "with_image": 0,
        "with_coordinates": 0,
        "generic_primary": 0,
        "missing_expected_fields": 0,
        "rescued_primary": 0,
    })

    entities_by_class = defaultdict(list)
    audit_buckets = defaultdict(list)

    for entity in data:
        primary = entity_primary_class(entity)
        rescued_primary, rescued, rescue_reason = apply_rescue_rules(entity, primary)
        if rescued:
            primary = rescued_primary
            rescued_count += 1
            rescued_copy = dict(entity)
            rescued_copy["_rescue_reason"] = rescue_reason
            rescued_copy["_rescued_primary_class"] = rescued_primary
            audit_buckets["rescued_entities"].append(rescued_copy)

        quality = class_quality(primary)
        primary_quality_counter[quality] += 1

        specific = entity_specific_classes(entity)
        if primary not in specific and quality == "specific":
            specific = list(dict.fromkeys(specific + [primary]))

        if len(specific) >= 2:
            ambiguous_count += 1
            pair = tuple(sorted(specific[:2]))
            ambiguous_pair_counter[pair] += 1
            audit_buckets["ambiguous_entities"].append(entity)

        if has_class_conflict(entity):
            conflict_count += 1
            audit_buckets["class_conflicts"].append(entity)

        missing_expected = entity_missing_expected_fields(entity, primary)
        if missing_expected:
            low_completeness_count += 1
            missing_copy = dict(entity)
            missing_copy["_primary_class"] = primary
            missing_copy["_missing_expected_fields"] = missing_expected
            audit_buckets["missing_expected_fields"].append(missing_copy)

        if quality == "missing":
            audit_buckets["missing_type"].append(entity)
        elif quality == "generic":
            audit_buckets["generic_only"].append(entity)

        classes = entity_all_classes(entity) if multi_class else [primary]

        for cls in classes:
            stats_by_class[cls]["total"] += 1
            if has_image(entity):
                stats_by_class[cls]["with_image"] += 1
            if has_coordinates(entity):
                stats_by_class[cls]["with_coordinates"] += 1
            if quality == "generic":
                stats_by_class[cls]["generic_primary"] += 1
            if missing_expected:
                stats_by_class[cls]["missing_expected_fields"] += 1
            if rescued:
                stats_by_class[cls]["rescued_primary"] += 1

            entities_by_class[cls].append(entity)

    if dup_groups:
        duplicate_candidates = []
        for _, items in dup_groups.items():
            duplicate_candidates.extend(items)
        audit_buckets["duplicate_candidates"] = duplicate_candidates
        audit_buckets["duplicate_groups"] = [
            {"dedupe_key": key, "count": len(items), "entities": items}
            for key, items in dup_groups.items()
        ]

    return {
        "summary": {
            "total_raw_entities": total,
            "total_unique_entities_estimated": dup_stats["total_unique_entities_estimated"],
            "duplicate_entities_estimated": dup_stats["duplicate_entities_estimated"],
            "duplicate_groups": dup_stats["duplicate_groups"],
            "with_image": total_with_image,
            "with_coordinates": total_with_coordinates,
            "primary_class_quality": dict(primary_quality_counter),
            "class_conflicts": conflict_count,
            "ambiguous_entities": ambiguous_count,
            "rescued_entities": rescued_count,
            "entities_with_missing_expected_fields": low_completeness_count,
            "top_ambiguous_pairs": [
                {"pair": list(pair), "count": count}
                for pair, count in ambiguous_pair_counter.most_common(20)
            ],
            "stats_by_class": dict(stats_by_class),
        },
        "stats_by_class": stats_by_class,
        "entities_by_class": entities_by_class,
        "audit_buckets": audit_buckets,
        "ambiguous_pair_counter": ambiguous_pair_counter,
    }