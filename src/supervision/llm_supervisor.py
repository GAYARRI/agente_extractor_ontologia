from __future__ import annotations

import json
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

from openai import OpenAI

from src.ontology.type_normalizer import normalize_type
from src.supervision.gold.examples import (
    candidate_vs_gold_score,
    load_gold_examples,
    normalize_url,
)
from src.utils.json_utils import safe_load_json


class LLMSupervisor:
    GENERIC_REJECT_CLASSES = {
        "",
        "thing",
        "location",
        "place",
        "person",
        "entity",
        "resource",
        "tourismentity",
        "organization",
        "localbusiness",
    }

    BAD_ENTITY_PATTERNS = [
        r"\bfacebook\b",
        r"\binstagram\b",
        r"\bsuscrib",
        r"\bmapas\b",
        r"\bconsignas\b",
        r"\bplanes\b",
        r"\bagenda\b",
        r"\bmultitud\b",
        r"\bfamilia\b",
        r"\bgastronomi",
        r"\bcultura\b",
        r"\btradiciones\b",
        r"\bdesarrollo sostenible\b",
        r"\binteres turistico internacional\b",
        r"\bturismo responsable\b",
        r"\bdescubre\b",
        r"\bver\b",
    ]

    BAD_EXACT_ENTITIES = {
        "facebook instagram",
        "agenda multitud",
        "pamplona ver",
        "planes excursiones",
        "planes cultura",
        "turismo responsable",
        "desarrollo sostenible",
        "interes turistico internacional",
    }

    EXTRACTION_SYSTEM_PROMPT = """
You are Role 1: tourism entity extractor.
Extract only concrete tourism-relevant named entities from the provided text.
Reject UI labels, slogans, headings, navigation, generic concepts, abstract topics,
cut fragments, duplicated text, and non-tourism technical terms.
Return only JSON.
""".strip()

    VALIDATION_SYSTEM_PROMPT = """
You are Role 2: tourism entity validator.
Keep only candidate entities that are concrete, named, and genuinely relevant to tourism.
Reject abstract concepts, editorial fragments, generic activities, technical phrases,
partial institution names, duplicated entities, and web navigation text.
Return only JSON.
""".strip()

    CLASSIFICATION_SYSTEM_PROMPT = """
You are Role 3: ontology classifier for tourism entities.
Classify only valid entities and assign a single specific ontology class from the allowed set.
Use the entity name as the primary signal. Use context only to confirm or disambiguate.
Reject doubtful, generic, editorial, technical, or narrative candidates.
Never output generic classes such as Thing, Place, Location, Person, Entity, Resource, or Organization.
Return only JSON.
""".strip()

    DEFAULT_POSITIVE_FEW_SHOTS = [
        {
            "input": {
                "name": "Catedral de Santa Maria la Real",
                "url": "https://visitpamplonairuna.com/lugar/catedral-de-santa-maria-la-real/",
                "page_context": "Catedral gotica de referencia en Pamplona.",
            },
            "output": {
                "entity": "Catedral de Santa Maria la Real",
                "class": "Cathedral",
                "score": 0.91,
                "short_description": "Catedral gotica principal de Pamplona.",
                "long_description": "Conjunto catedralicio historico y visitable con claro valor patrimonial.",
                "reason": "Nombre de POI claro y contexto plenamente coherente con una catedral.",
            },
        },
        {
            "input": {
                "name": "San Fermin",
                "url": "https://visitpamplonairuna.com/descubre-pamplona/san-fermin/",
                "page_context": "Fiesta principal de Pamplona, con encierros y programa festivo.",
            },
            "output": {
                "entity": "San Fermin",
                "class": "Event",
                "score": 0.92,
                "short_description": "Fiesta principal y evento turistico de Pamplona.",
                "long_description": "Celebracion con identidad propia y gran interes turistico asociada a los encierros.",
                "reason": "Nombre de evento concreto y de alta notoriedad turistica.",
            },
        },
        {
            "input": {
                "name": "Mercado de Santo Domingo",
                "url": "https://visitpamplonairuna.com/mercados-imprescindibles-pamplona/",
                "page_context": "Mercado tradicional en Pamplona con producto local.",
            },
            "output": {
                "entity": "Mercado de Santo Domingo",
                "class": "TraditionalMarket",
                "score": 0.87,
                "short_description": "Mercado tradicional de producto local en Pamplona.",
                "long_description": "Mercado identificable y visitable, claramente alineado con un recurso gastronomico local.",
                "reason": "Entidad concreta y visitable con fuerte senal lexical de mercado tradicional.",
            },
        },
        {
            "input": {
                "name": "OleoturJaen",
                "url": "https://www.jaenparaisointerior.es/es/oleotour/inicio",
                "page_context": "Experiencia de oleoturismo vinculada a la cultura del olivo.",
            },
            "output": {
                "entity": "OleoturJaen",
                "class": "DestinationExperience",
                "score": 0.89,
                "short_description": "Experiencia turistica tematica centrada en el aceite y el olivo.",
                "long_description": "Oferta de experiencia turistica vinculada al oleoturismo y al conocimiento del territorio.",
                "reason": "Marca de experiencia turistica concreta, no un concepto abstracto.",
            },
        },
    ]

    DEFAULT_NEGATIVE_FEW_SHOTS = [
        {
            "input": {
                "name": "Descubre Pamplona",
                "url": "https://ejemplo.com/descubre-pamplona",
                "page_context": "Texto editorial del portal.",
            },
            "output": {
                "reject": True,
                "reason": "Lema editorial o heading del portal, no entidad concreta.",
            },
        },
        {
            "input": {
                "name": "tecnologias agroalimentarias",
                "url": "https://ejemplo.com/mercado-basotxoa",
                "page_context": "Texto tecnico e institucional, no recurso turistico visitable.",
            },
            "output": {
                "reject": True,
                "reason": "Sintagma tecnico abstracto sin interes turistico propio.",
            },
        },
    ]

    DEFAULT_AMBIGUOUS_FEW_SHOTS = [
        {
            "input": {
                "name": "Casco Antiguo de Pamplona",
                "url": "https://ejemplo.com/casco-antiguo",
                "page_context": "Zona historica urbana con identidad espacial clara.",
            },
            "output": {
                "entity": "Casco Antiguo de Pamplona",
                "class": "Neighborhood",
                "score": 0.82,
                "short_description": "Barrio o zona historica identificable de Pamplona.",
                "long_description": "Entidad urbana concreta y reconocible, valida si el texto la trata como espacio visitable con identidad propia.",
                "reason": "Caso limite aceptable solo cuando el contexto confirma una entidad urbana concreta.",
            },
        },
        {
            "input": {
                "name": "Pelota Vasca",
                "url": "https://ejemplo.com/pelota-vasca",
                "page_context": "Concepto deportivo general.",
            },
            "output": {
                "reject": True,
                "reason": "Concepto cultural o deportivo general, no POI ni evento concreto.",
            },
        },
    ]

    def __init__(
        self,
        ontology_index=None,
        model: str = "gpt-5.4-mini",
        gold_examples_path: str = "benchmark/Ejemplos.csv",
        use_fewshots: bool = False,
        fewshots: Optional[List[dict]] = None,
    ):
        self.ontology_index = ontology_index
        self.model = model
        self.use_fewshots = bool(use_fewshots)
        self.custom_fewshots = fewshots or []

        try:
            self.client = OpenAI()
        except Exception as exc:
            print(f"[LLM_SUPERVISOR] LLM no disponible: {exc}", file=sys.stderr)
            self.client = None

        try:
            self.gold_examples = load_gold_examples(gold_examples_path)
            print(f"[LLM_SUPERVISOR] Golden examples cargados: {len(self.gold_examples)}", file=sys.stderr)
        except Exception as exc:
            print(f"[LLM_SUPERVISOR][WARN] No se pudieron cargar golden examples: {exc}", file=sys.stderr)
            self.gold_examples = {}

        self.allowed_classes = self._load_allowed_classes()
        self.allowed_class_lookup = self._build_allowed_class_lookup(self.allowed_classes)
        self.positive_few_shots, self.negative_few_shots, self.ambiguous_few_shots = self._prepare_few_shots()

    def _build_allowed_class_lookup(self, allowed_classes: Iterable[str]) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for cls in allowed_classes or []:
            raw = str(cls or "").strip()
            if not raw:
                continue
            lookup[raw.lower()] = raw
            norm = normalize_type(raw).strip().lower()
            if norm:
                lookup[norm] = raw
        return lookup

    def _canonicalize_class(self, value: str) -> str:
        if not value:
            return ""

        raw = str(value).strip()
        if not raw:
            return ""

        raw_lower = raw.lower()
        norm = normalize_type(raw).strip().lower()

        aliases = {
            "evento": "Event",
            "monumento": "Monument",
            "organization": "TourismOrganisation",
            "touristinformationoffice": "TouristInformationOffice",
        }
        if raw_lower in aliases:
            return aliases[raw_lower]
        if norm in aliases:
            return aliases[norm]

        if self.allowed_class_lookup:
            return self.allowed_class_lookup.get(raw_lower, "") or self.allowed_class_lookup.get(norm, "")

        return raw

    def _is_generic_class(self, class_name: str) -> bool:
        raw = str(class_name or "").strip()
        if not raw:
            return True

        raw_lower = raw.lower()
        norm = normalize_type(raw).strip().lower()
        return raw_lower in self.GENERIC_REJECT_CLASSES or norm in self.GENERIC_REJECT_CLASSES

    def _load_allowed_classes(self) -> set[str]:
        allowed = set()

        if isinstance(self.ontology_index, dict):
            allowed.update(str(key).strip() for key in self.ontology_index.keys() if str(key).strip())
        elif hasattr(self.ontology_index, "classes"):
            classes_obj = getattr(self.ontology_index, "classes")
            if isinstance(classes_obj, dict):
                allowed.update(str(key).strip() for key in classes_obj.keys() if str(key).strip())
            elif isinstance(classes_obj, list):
                for item in classes_obj:
                    if isinstance(item, str) and item.strip():
                        allowed.add(item.strip())
                    elif isinstance(item, dict) and item.get("name"):
                        allowed.add(str(item["name"]).strip())
        elif hasattr(self.ontology_index, "get_all_classes"):
            try:
                for item in self.ontology_index.get_all_classes():
                    if isinstance(item, str) and item.strip():
                        allowed.add(item.strip())
                    elif isinstance(item, dict) and item.get("name"):
                        allowed.add(str(item["name"]).strip())
            except Exception:
                pass

        return {cls for cls in allowed if cls}

    def _coerce_fewshot_bucket(self, example: dict) -> str:
        output = example.get("output", {}) if isinstance(example, dict) else {}
        if output.get("reject") is True:
            return "negative"

        label = str(example.get("bucket") or example.get("category") or example.get("role") or "").strip().lower()
        if label in {"positive", "negative", "ambiguous"}:
            return label

        return "positive"

    def _sanitize_fewshot(self, example: dict) -> Optional[dict]:
        if not isinstance(example, dict):
            return None

        raw_input = example.get("input")
        raw_output = example.get("output")
        if not isinstance(raw_input, dict) or not isinstance(raw_output, dict):
            return None

        clean_input = {
            "name": str(raw_input.get("name", "")).strip(),
            "url": str(raw_input.get("url", "")).strip(),
            "page_context": str(raw_input.get("page_context", "")).strip(),
        }
        if not clean_input["name"]:
            return None

        clean_output = dict(raw_output)
        if clean_output.get("reject") is True:
            clean_output = {
                "reject": True,
                "reason": str(clean_output.get("reason", "")).strip()[:220],
            }
            return {"input": clean_input, "output": clean_output}

        canonical_class = self._canonicalize_class(str(clean_output.get("class", "")).strip())
        if not canonical_class or self._is_generic_class(canonical_class):
            return None

        clean_output = {
            "entity": str(clean_output.get("entity") or clean_input["name"]).strip(),
            "class": canonical_class,
            "score": max(0.0, min(float(clean_output.get("score", 0.85) or 0.85), 0.95)),
            "short_description": str(clean_output.get("short_description", "")).strip()[:160],
            "long_description": str(clean_output.get("long_description", "")).strip()[:400],
            "reason": str(clean_output.get("reason", "")).strip()[:220],
        }
        if not clean_output["entity"]:
            return None

        return {"input": clean_input, "output": clean_output}

    def _prepare_few_shots(self) -> Tuple[List[dict], List[dict], List[dict]]:
        source_examples = self.custom_fewshots if self.custom_fewshots else (
            self.DEFAULT_POSITIVE_FEW_SHOTS + self.DEFAULT_NEGATIVE_FEW_SHOTS + self.DEFAULT_AMBIGUOUS_FEW_SHOTS
        )

        positives: List[dict] = []
        negatives: List[dict] = []
        ambiguous: List[dict] = []

        for example in source_examples:
            clean = self._sanitize_fewshot(example)
            if not clean:
                continue

            bucket = self._coerce_fewshot_bucket(example)
            if bucket == "negative":
                negatives.append(clean)
            elif bucket == "ambiguous":
                ambiguous.append(clean)
            else:
                positives.append(clean)

        return positives, negatives, ambiguous

    def safe_json_parse(self, content):
        if not content:
            return []

        content = content.strip()
        content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"^```\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        try:
            return safe_load_json(content)
        except Exception:
            pass

        match = re.search(r"(\{.*\}|\[.*\])", content, re.DOTALL)
        if match:
            try:
                return safe_load_json(match.group(1))
            except Exception:
                pass

        return []

    def build_ontology_context(self, max_classes: int = 80) -> str:
        class_lines = []

        if isinstance(self.ontology_index, dict):
            for idx, (cls, meta) in enumerate(self.ontology_index.items()):
                if idx >= max_classes:
                    break
                if isinstance(meta, dict):
                    label = meta.get("label")
                    parents = meta.get("parents") or []
                    if label:
                        class_lines.append(f"- {cls}: {label}")
                    elif parents:
                        class_lines.append(f"- {cls}: parents={', '.join(str(p) for p in parents[:3])}")
                    else:
                        class_lines.append(f"- {cls}")
                else:
                    class_lines.append(f"- {cls}")
        elif hasattr(self.ontology_index, "classes") and isinstance(getattr(self.ontology_index, "classes"), dict):
            for idx, (cls, desc) in enumerate(getattr(self.ontology_index, "classes").items()):
                if idx >= max_classes:
                    break
                class_lines.append(f"- {cls}: {desc}")

        if not class_lines and self.allowed_classes:
            for cls in sorted(self.allowed_classes)[:max_classes]:
                class_lines.append(f"- {cls}")

        return "\n".join(class_lines)

    def normalize_llm_class(self, value: str) -> str:
        canonical = self._canonicalize_class(value)
        return normalize_type(canonical or value)

    def build_gold_example_prompt_context(self, url: str) -> str:
        if not url:
            return ""

        url_norm = normalize_url(url)
        gold_case = self.gold_examples.get(url_norm)
        if not gold_case:
            return ""

        gold_entity = gold_case.get("entity", "")
        gold_type = self._canonicalize_class(gold_case.get("type", "")) or gold_case.get("type", "")
        if not gold_entity:
            return ""

        return f"""
RELEVANT SUPERVISED EXAMPLE FOR THIS URL:
- URL: {url_norm}
- Expected main entity: {gold_entity}
- Expected ontology class: {gold_type}

Use this only as a ranking prior when it matches the actual page text.
Do not copy it blindly if the text clearly says otherwise.
""".strip()

    def apply_gold_prior(self, url: str, candidates: list[dict]) -> list[dict]:
        url_norm = normalize_url(url)
        gold_case = self.gold_examples.get(url_norm)
        if not gold_case:
            return candidates

        enriched = []
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            new_cand = dict(cand)
            new_cand["gold_alignment_score"] = candidate_vs_gold_score(cand, gold_case)
            enriched.append(new_cand)

        enriched.sort(
            key=lambda item: (
                item.get("gold_alignment_score", 0.0),
                item.get("score", 0.0),
            ),
            reverse=True,
        )

        print(f"[LLM_SUPERVISOR][GOLD] URL conocida: {url_norm}", file=sys.stderr)
        return enriched

    def rerank_classified_entities(self, url: str, items: list[dict]) -> list[dict]:
        if not items:
            return items

        candidates = []
        for item in items:
            if not isinstance(item, dict):
                continue
            candidate = dict(item)
            candidate["entity_name"] = item.get("entity", "")
            candidate["normalized_type"] = item.get("normalized_type", "") or self.normalize_llm_class(item.get("class", ""))
            candidates.append(candidate)

        reranked = self.apply_gold_prior(url, candidates)
        clean_items = []
        for item in reranked:
            clean_items.append({
                "entity": item.get("entity", ""),
                "class": item.get("class", ""),
                "score": item.get("score", 0.5),
                "short_description": item.get("short_description", ""),
                "long_description": item.get("long_description", ""),
                "gold_alignment_score": item.get("gold_alignment_score", 0.0),
                "normalized_type": item.get("normalized_type", ""),
                "reason": item.get("reason", ""),
            })
        return clean_items

    def _format_few_shot_examples(self, title: str, examples: list[dict]) -> str:
        if not examples:
            return ""

        lines = [title]
        for idx, example in enumerate(examples, start=1):
            lines.append(f"\nExample {idx}")
            lines.append("INPUT:")
            lines.append(json.dumps(example.get("input", {}), ensure_ascii=False, indent=2))
            lines.append("OUTPUT:")
            lines.append(json.dumps(example.get("output", {}), ensure_ascii=False, indent=2))
        return "\n".join(lines)

    def build_few_shot_prompt_context(self) -> str:
        if not self.use_fewshots:
            return ""

        parts = [
            self._format_few_shot_examples("POSITIVE EXAMPLES", self.positive_few_shots),
            self._format_few_shot_examples("NEGATIVE EXAMPLES", self.negative_few_shots),
            self._format_few_shot_examples("AMBIGUOUS EXAMPLES", self.ambiguous_few_shots),
        ]
        return "\n\n".join(part for part in parts if part.strip())

    def normalize_entity_text(self, value: str) -> str:
        value = str(value or "").strip()
        return re.sub(r"\s+", " ", value)

    def is_bad_entity_name(self, entity: str) -> bool:
        entity = self.normalize_entity_text(entity)
        if not entity:
            return True

        entity_l = entity.lower()
        if entity_l in self.BAD_EXACT_ENTITIES:
            return True
        if len(entity) < 3:
            return True
        if len(entity.split()) > 9:
            return True
        if re.fullmatch(r"[\W\d_]+", entity):
            return True
        if re.search(r"\b(siglos?|origen|historia|haz clic)\b", entity_l):
            return True
        for pattern in self.BAD_ENTITY_PATTERNS:
            if re.search(pattern, entity_l, flags=re.IGNORECASE):
                return True

        tokens = entity_l.split()
        return len(tokens) >= 2 and len(set(tokens)) == 1

    def dedupe_entities(self, entities: list[str]) -> list[str]:
        seen = set()
        clean = []

        for entity in entities:
            entity = self.normalize_entity_text(entity)
            key = entity.lower()
            if not entity or key in seen:
                continue
            seen.add(key)
            clean.append(entity)
        return clean

    def is_valid_class(self, class_name: str) -> bool:
        canonical = self._canonicalize_class(class_name)
        if not canonical or self._is_generic_class(canonical):
            return False
        if self.allowed_classes and canonical not in self.allowed_classes:
            return False
        return True

    def calibrate_score(self, entity: str, class_name: str, llm_score: float) -> float:
        score = max(0.0, min(1.0, float(llm_score)))
        if self.is_bad_entity_name(entity):
            score *= 0.15
        if not self.is_valid_class(class_name):
            score *= 0.10
        if len(entity.split()) == 1:
            score *= 0.80
        if score > 0.95:
            score = 0.92
        return round(score, 4)

    def filter_classified_items(self, items: list[dict]) -> list[dict]:
        filtered = []
        seen = set()

        for item in items:
            entity = self.normalize_entity_text(item.get("entity", ""))
            entity_class = self._canonicalize_class(item.get("class", ""))
            score = float(item.get("score", 0.0) or 0.0)

            if not entity or not entity_class:
                continue
            if self.is_bad_entity_name(entity):
                continue
            if not self.is_valid_class(entity_class):
                continue
            if score < 0.45:
                continue

            key = (entity.lower(), entity_class.lower())
            if key in seen:
                continue
            seen.add(key)

            new_item = dict(item)
            new_item["entity"] = entity
            new_item["class"] = entity_class
            new_item["normalized_type"] = normalize_type(entity_class)
            filtered.append(new_item)

        return filtered

    def build_extraction_prompt(self, text: str) -> str:
        return f"""
Extract only concrete tourism entities from the following text.

TEXT:
\"\"\"
{text}
\"\"\"

Return JSON only:
{{
  "entities": ["Entity 1", "Entity 2"]
}}
""".strip()

    def build_validation_prompt(self, entities: list[str], text: str) -> str:
        entities_json = json.dumps(entities, ensure_ascii=False)
        return f"""
Validate the candidate entities against the text and keep only real tourism entities.

TEXT:
\"\"\"
{text}
\"\"\"

CANDIDATES:
{entities_json}

Return JSON only:
{{
  "entities": ["Valid entity 1", "Valid entity 2"]
}}
""".strip()

    def build_classification_prompt(self, entities: list[str], text: str, url: Optional[str] = None) -> str:
        entities_json = json.dumps(entities, ensure_ascii=False)
        ontology_context = self.build_ontology_context()
        gold_context = self.build_gold_example_prompt_context(url) if url else ""
        few_shot_context = self.build_few_shot_prompt_context()
        allowed_classes_line = ", ".join(sorted(self.allowed_classes)) if self.allowed_classes else "Use only ontology classes."

        return f"""
ALLOWED CLASSES:
{allowed_classes_line}

ONTOLOGY CONTEXT:
{ontology_context}

{gold_context}

{few_shot_context}

TEXT:
\"\"\"
{text}
\"\"\"

CANDIDATE ENTITIES:
{entities_json}

Return JSON only:
{{
  "entities": [
    {{
      "entity": "Exact entity name",
      "class": "OntologyClass",
      "score": 0.0,
      "short_description": "Brief description",
      "long_description": "Slightly longer description",
      "reason": "Short reason"
    }}
  ]
}}
""".strip()

    def call_llm_json(self, prompt: str, default=None, system_prompt: str = ""):
        if default is None:
            default = []
        if self.client is None:
            return default

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
            )
            content = response.choices[0].message.content.strip()
            return self.safe_json_parse(content)
        except Exception as exc:
            print(f"[LLM_SUPERVISOR] LLM error: {exc}", file=sys.stderr)
            return default

    def extract_entities(self, text: str) -> list[str]:
        prompt = self.build_extraction_prompt(text)
        data = self.call_llm_json(prompt, default={"entities": []}, system_prompt=self.EXTRACTION_SYSTEM_PROMPT)

        if isinstance(data, dict):
            entities = data.get("entities", [])
            if isinstance(entities, list):
                entities = [str(entity).strip() for entity in entities if str(entity).strip()]
                entities = self.dedupe_entities(entities)
                entities = [entity for entity in entities if not self.is_bad_entity_name(entity)]
                return entities
        return []

    def validate_entities(self, entities: list[str], text: str) -> list[str]:
        if not entities:
            return []

        prompt = self.build_validation_prompt(entities, text)
        data = self.call_llm_json(prompt, default={"entities": []}, system_prompt=self.VALIDATION_SYSTEM_PROMPT)

        if isinstance(data, dict):
            clean_entities = data.get("entities", [])
            if isinstance(clean_entities, list):
                clean_entities = [str(entity).strip() for entity in clean_entities if str(entity).strip()]
                clean_entities = self.dedupe_entities(clean_entities)
                clean_entities = [entity for entity in clean_entities if not self.is_bad_entity_name(entity)]
                return clean_entities
        return []

    def analyze_entities(self, entities: list[str], text: str, url: Optional[str] = None) -> list[dict]:
        if not entities:
            return []

        entities = self.dedupe_entities(entities)
        entities = [entity for entity in entities if not self.is_bad_entity_name(entity)]
        if not entities:
            return []

        if url and normalize_url(url) in self.gold_examples:
            print(f"[LLM_SUPERVISOR][PROMPT_GOLD] usando ejemplo supervisado para {normalize_url(url)}", file=sys.stderr)

        prompt = self.build_classification_prompt(entities, text, url=url)
        data = self.call_llm_json(prompt, default={"entities": []}, system_prompt=self.CLASSIFICATION_SYSTEM_PROMPT)

        if isinstance(data, dict):
            items = data.get("entities", [])
            if isinstance(items, list):
                clean_items = []
                for item in items:
                    if not isinstance(item, dict):
                        continue

                    entity = self.normalize_entity_text(item.get("entity", ""))
                    entity_class = self._canonicalize_class(item.get("class", ""))
                    if not entity or not entity_class:
                        continue

                    try:
                        raw_score = float(item.get("score", 0.5))
                    except Exception:
                        raw_score = 0.5

                    clean_items.append({
                        "entity": entity,
                        "class": entity_class,
                        "normalized_type": normalize_type(entity_class),
                        "score": self.calibrate_score(entity, entity_class, raw_score),
                        "short_description": str(item.get("short_description", "")).strip()[:160],
                        "long_description": str(item.get("long_description", "")).strip()[:400],
                        "reason": str(item.get("reason", "")).strip()[:220],
                    })

                clean_items = self.filter_classified_items(clean_items)
                if url:
                    clean_items = self.rerank_classified_entities(url, clean_items)
                return clean_items
        return []

    def extract_and_validate_entities(self, text: str) -> list[str]:
        return self.validate_entities(self.extract_entities(text), text)

    def final_entity_guard(self, entities: list[dict]) -> list[dict]:
        filtered = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue

            name = self.normalize_entity_text(entity.get("name", "") or entity.get("entity", ""))
            class_name = self._canonicalize_class(entity.get("class", "") or entity.get("type", ""))
            if not name or self.is_bad_entity_name(name):
                continue
            if not self.is_valid_class(class_name):
                continue

            new_entity = dict(entity)
            new_entity["name"] = name
            new_entity["class"] = class_name
            new_entity["type"] = class_name
            new_entity["types"] = [class_name]

            try:
                new_entity["score"] = min(float(new_entity.get("score", 0.5)), 0.9)
            except Exception:
                new_entity["score"] = 0.5

            filtered.append(new_entity)
        return filtered
