import csv
import re
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from src.ontology.type_normalizer import normalize_type


def normalize_text(value: str) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = str(url).strip().lower()
    url = url.replace("http://", "https://")
    if "#" in url:
        url = url.split("#")[0]
    url = url.rstrip("/")
    return url



def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_type(a), normalize_type(b)).ratio()


def load_gold_examples(csv_path: str) -> dict:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de ejemplos: {path}")

    gold = {}

    with open(path, "r", encoding="utf-8-sig") as f:
        sample = f.read(2048)
        f.seek(0)

        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            url = normalize_url(row.get("url", ""))
            entity = normalize_type(row.get("Entity", ""))
            etype = normalize_type(row.get("Type", ""))

            if not url or not entity:
                continue

            gold[url] = {
                "entity": entity,
                "type": etype,
            }

    return gold


def extract_candidate_name(candidate: dict) -> str:
    for field in ["entity_name", "entity", "name", "label", "title", "text"]:
        value = candidate.get(field)
        if isinstance(value, str) and value.strip():
            return normalize_type(value)

    props = candidate.get("properties")
    if isinstance(props, dict):
        for field in ["label", "name", "title"]:
            value = props.get(field)
            if isinstance(value, str) and value.strip():
                return normalize_type(value)

    return ""


def extract_candidate_type(candidate: dict) -> str:
    raw = None

    if "normalized_type" in candidate and candidate.get("normalized_type"):
        raw = candidate.get("normalized_type")
    elif "type" in candidate and candidate.get("type"):
        raw = candidate.get("type")
    elif "types" in candidate and candidate.get("types"):
        raw = candidate.get("types")
    elif "class" in candidate and candidate.get("class"):
        raw = candidate.get("class")

    if isinstance(raw, list):
        raw = raw[0] if raw else ""

    return normalize_type(raw)


def candidate_vs_gold_score(candidate: dict, gold_case: dict) -> float:
    cand_name = extract_candidate_name(candidate)
    cand_type = extract_candidate_type(candidate)

    gold_name = gold_case["entity"]
    gold_type = gold_case["type"]

    name_score = similarity(cand_name, gold_name)
    type_score = 1.0 if cand_type == gold_type and cand_type else 0.0

    return 0.80 * name_score + 0.20 * type_score


def apply_gold_prior(url: str, candidates: list[dict], gold_examples: dict) -> list[dict]:
    url_norm = normalize_url(url)
    gold_case = gold_examples.get(url_norm)

    if not gold_case:
        return candidates

    enriched = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue

        new_cand = dict(cand)
        new_cand["gold_alignment_score"] = candidate_vs_gold_score(cand, gold_case)
        enriched.append(new_cand)

    return sorted(
        enriched,
        key=lambda x: (
            x.get("gold_alignment_score", 0.0),
            x.get("qualityScore", 0),
            x.get("verisimilitude_score", 0),
            x.get("score", 0),
        ),
        reverse=True,
    )