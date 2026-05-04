from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entity_processing.normalize import normalize_text
from entity_processing.text_cleaning import contains_mojibake, contains_navigation_noise


PHYSICAL_CLASSES = {
    "Airport",
    "ArcheologicalSite",
    "Bar",
    "Basilica",
    "Bridge",
    "Camping",
    "Castle",
    "Cathedral",
    "Chapel",
    "Church",
    "Convent",
    "Garden",
    "Gate",
    "HistoricalOrCulturalResource",
    "Hostel",
    "Hotel",
    "Monastery",
    "Monument",
    "Museum",
    "Palace",
    "Park",
    "Restaurant",
    "Square",
    "Theatre",
    "Theater",
    "TownHall",
    "TraditionalMarket",
    "Wall",
}
SUSPICIOUS_NAME_TOKENS = {
    "continuamos",
    "cruzando",
    "datos api",
    " ir a ",
    " madrid",
}
TRUNCATED_TAILS = (" de", " del", " la", " el", " los", " las", " y")


def _coords_present(entity: dict) -> bool:
    coords = entity.get("coordinates") or {}
    if not isinstance(coords, dict):
        return False
    return coords.get("lat") is not None and coords.get("lng") is not None


def _image_value(entity: dict) -> str:
    return str(entity.get("mainImage") or entity.get("image") or "").strip()


def _is_generic_image(value: str) -> bool:
    low = value.lower()
    return any(token in low for token in ("desliza.png", "whatsapp", "facebook", "instagram", "youtube", "share"))


def _candidate_images(entity: dict) -> list:
    value = entity.get("candidateImages") or []
    return value if isinstance(value, list) else []


def _rejected_images(entity: dict) -> list:
    value = entity.get("rejectedImages") or []
    return value if isinstance(value, list) else []


def _quality_reasons(entity: dict) -> list[str]:
    value = entity.get("qualityReasons") or []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _looks_suspicious_name(entity: dict) -> bool:
    name = f" {normalize_text(entity.get('name') or '')} "
    stripped = name.strip()
    return (
        any(token in name for token in SUSPICIOUS_NAME_TOKENS)
        or stripped.endswith(TRUNCATED_TAILS)
        or stripped.startswith(("de ", "del ", "y "))
    )


def _review_bucket(entity: dict) -> str:
    if _looks_suspicious_name(entity):
        return "suspicious_name"
    if any(contains_navigation_noise(entity.get(field)) for field in ("description", "shortDescription", "longDescription")):
        return "navigation_noise"
    cls = str(entity.get("class") or "").strip()
    if cls in PHYSICAL_CLASSES and not _coords_present(entity):
        if not _image_value(entity):
            return "missing_geo_and_image"
        return "missing_geo"
    if not _image_value(entity):
        return "missing_image"
    if _candidate_images(entity) and not _image_value(entity):
        return "only_weak_image_candidates"
    return "manual_review"


def _review_analysis(entities: list[dict]) -> dict:
    reviews = [e for e in entities if str(e.get("qualityDecision") or "") == "review"]
    buckets = Counter(_review_bucket(e) for e in reviews)
    reasons = Counter()
    classes = Counter()
    geo_rejections = Counter()
    suspicious_samples = []
    for entity in reviews:
        classes[str(entity.get("class") or "")] += 1
        geo_rejections[str(entity.get("geoRejectedReason") or "")] += 1
        for reason in _quality_reasons(entity):
            reasons[reason] += 1
        if _looks_suspicious_name(entity) and len(suspicious_samples) < 20:
            suspicious_samples.append(
                {
                    "name": str(entity.get("name") or ""),
                    "class": str(entity.get("class") or ""),
                    "score": entity.get("finalScore"),
                    "sourceUrl": str(entity.get("sourceUrl") or entity.get("url") or ""),
                }
            )

    return {
        "totalReview": len(reviews),
        "reviewBuckets": dict(buckets.most_common()),
        "reviewReasons": dict(reasons.most_common()),
        "reviewClasses": dict(classes.most_common()),
        "reviewGeoRejectedReasons": dict(geo_rejections.most_common()),
        "suspiciousReviewSamples": suspicious_samples,
    }


def build_metrics(entities: list[dict]) -> dict:
    names = [str(e.get("name") or "").strip() for e in entities]
    classes = [str(e.get("class") or "").strip() for e in entities]
    dup_names = Counter(normalize_text(name) for name in names if name)
    images = Counter(_image_value(e) for e in entities if _image_value(e))
    final_scores = [float(e.get("finalScore")) for e in entities if e.get("finalScore") not in (None, "")]
    quality_decisions = Counter(str(e.get("qualityDecision") or "") for e in entities)
    geo_sources = Counter(str(e.get("geoSource") or "") for e in entities)
    geo_rejections = Counter(str(e.get("geoRejectedReason") or "") for e in entities)
    rejected_reasons = Counter()
    for entity in entities:
        for item in _rejected_images(entity):
            if isinstance(item, dict):
                rejected_reasons[str(item.get("reason") or item.get("rejectionReason") or "")] += 1

    metrics = {
        "totalEntities": len(entities),
        "emptyClass": sum(1 for cls in classes if not cls),
        "ontologyFalse": sum(1 for e in entities if e.get("ontologyMatch") is not True),
        "missingCoordinates": sum(1 for e in entities if not _coords_present(e)),
        "emptyDescription": sum(1 for e in entities if not str(e.get("description") or "").strip()),
        "missingImage": sum(1 for e in entities if not _image_value(e)),
        "genericImage": sum(1 for e in entities if _is_generic_image(_image_value(e))),
        "unverifiedImage": sum(1 for e in entities if str(e.get("imageQuality") or "") == "unverified"),
        "withCandidateImages": sum(1 for e in entities if _candidate_images(e)),
        "withRejectedImages": sum(1 for e in entities if _rejected_images(e)),
        "rejectedImageReasons": dict(rejected_reasons.most_common()),
        "mojibakeText": sum(
            1
            for e in entities
            if any(contains_mojibake(e.get(field)) for field in ("name", "description", "shortDescription", "longDescription"))
        ),
        "navigationNoise": sum(
            1
            for e in entities
            if any(contains_navigation_noise(e.get(field)) for field in ("description", "shortDescription", "longDescription"))
        ),
        "duplicateNameGroups": sum(1 for _, count in dup_names.items() if count > 1),
        "avgFinalScore": round(sum(final_scores) / len(final_scores), 2) if final_scores else None,
        "qualityDecisions": dict(quality_decisions.most_common()),
        "geoSources": dict(geo_sources.most_common()),
        "geoRejectedReasons": dict(geo_rejections.most_common()),
        "topDuplicateNames": [
            {"name": name, "count": count}
            for name, count in dup_names.most_common(20)
            if count > 1
        ],
        "classes": dict(Counter(classes).most_common()),
        "topImages": [
            {"image": image, "count": count}
            for image, count in images.most_common(15)
        ],
    }
    metrics["reviewAnalysis"] = _review_analysis(entities)
    return metrics


def write_markdown(path: Path, metrics: dict) -> None:
    lines = [
        "# Entity Quality Audit",
        "",
        f"- Total entities: `{metrics['totalEntities']}`",
        f"- Empty class: `{metrics['emptyClass']}`",
        f"- Ontology false: `{metrics['ontologyFalse']}`",
        f"- Missing coordinates: `{metrics['missingCoordinates']}`",
        f"- Missing image: `{metrics['missingImage']}`",
        f"- Generic image: `{metrics['genericImage']}`",
        f"- Unverified image: `{metrics['unverifiedImage']}`",
        f"- With candidate images: `{metrics['withCandidateImages']}`",
        f"- With rejected images: `{metrics['withRejectedImages']}`",
        f"- Mojibake text: `{metrics['mojibakeText']}`",
        f"- Navigation noise: `{metrics['navigationNoise']}`",
        f"- Duplicate name groups: `{metrics['duplicateNameGroups']}`",
        f"- Avg final score: `{metrics['avgFinalScore']}`",
        "",
        "## Quality decisions",
        "",
    ]
    for decision, count in metrics["qualityDecisions"].items():
        lines.append(f"- `{decision or 'EMPTY'}`: `{count}`")
    lines.extend(
        [
            "",
            "## Geo rejected reasons",
            "",
        ]
    )
    for reason, count in metrics["geoRejectedReasons"].items():
        lines.append(f"- `{reason or 'EMPTY'}`: `{count}`")
    lines.extend(["", "## Rejected image reasons", ""])
    for reason, count in metrics["rejectedImageReasons"].items():
        lines.append(f"- `{reason or 'EMPTY'}`: `{count}`")
    lines.extend(["", "## Review analysis", ""])
    review = metrics.get("reviewAnalysis") or {}
    lines.append(f"- Total review: `{review.get('totalReview', 0)}`")
    lines.append("")
    lines.append("### Review buckets")
    lines.append("")
    for bucket, count in (review.get("reviewBuckets") or {}).items():
        lines.append(f"- `{bucket}`: `{count}`")
    lines.append("")
    lines.append("### Suspicious review samples")
    lines.append("")
    for row in review.get("suspiciousReviewSamples") or []:
        lines.append(f"- `{row['name']}` (`{row['class']}`, score `{row['score']}`): {row['sourceUrl']}")
    lines.extend([
        "",
        "## Top duplicate names",
        "",
    ])
    for row in metrics["topDuplicateNames"]:
        lines.append(f"- `{row['name']}`: `{row['count']}`")
    lines.extend(["", "## Top classes", ""])
    for cls, count in list(metrics["classes"].items())[:20]:
        lines.append(f"- `{cls or 'EMPTY'}`: `{count}`")
    lines.extend(["", "## Top images", ""])
    for row in metrics["topImages"]:
        lines.append(f"- `{row['count']}`: {row['image']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit entity extraction quality metrics.")
    parser.add_argument("--entities", default="entities.json")
    parser.add_argument("--json-output", default="entity_audit/latest_quality_metrics.json")
    parser.add_argument("--md-output", default="entity_audit/latest_quality_report.md")
    args = parser.parse_args()

    entities = json.loads(Path(args.entities).read_text(encoding="utf-8"))
    metrics = build_metrics(entities)

    json_path = Path(args.json_output)
    md_path = Path(args.md_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(md_path, metrics)

    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
