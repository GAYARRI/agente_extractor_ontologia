import json
import os
import re
from openai import OpenAI


class RelationExtractor:
    def __init__(self, properties=None):
        self.properties = properties if properties else []

        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None

        # patrones simples
        self.patterns = [
            ("locatedIn", r"(.+?)\s+se encuentra en\s+(.+)"),
            ("locatedIn", r"(.+?)\s+está en\s+(.+)"),
            ("locatedIn", r"(.+?)\s+ubicado en\s+(.+)"),
            ("locatedIn", r"(.+?)\s+ubicada en\s+(.+)"),
            ("partOf", r"(.+?)\s+forma parte de\s+(.+)"),
            ("hasEvent", r"(.+?)\s+celebra\s+(.+)"),
        ]

    def _normalize(self, text: str) -> str:
        return " ".join(text.strip().lower().split())

    def _entity_map(self, entities):
        """
        entities esperado:
        [
            {
                "text": "...",
                "uri": ...,
                "class": "...",
                "confidence": ...
            }
        ]
        """
        entity_map = {}
        for e in entities:
            text = e.get("text")
            if text:
                entity_map[self._normalize(text)] = e
        return entity_map

    def _split_sentences(self, text):
        return re.split(r"[.!?\n]+", text)

    # ----------------------------------------
    # REGLAS
    # ----------------------------------------

    def extract_rules(self, entities, text):
        relations = []
        entity_map = self._entity_map(entities)
        sentences = self._split_sentences(text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            for predicate, pattern in self.patterns:
                match = re.search(pattern, sentence, re.IGNORECASE)
                if not match:
                    continue

                subject_candidate = match.group(1).strip(" ,;:()[]\"'")
                object_candidate = match.group(2).strip(" ,;:()[]\"'")

                subject_norm = self._normalize(subject_candidate)
                object_norm = self._normalize(object_candidate)

                # solo aceptamos si el sujeto y objeto coinciden con entidades detectadas
                if subject_norm in entity_map and object_norm in entity_map:
                    relations.append(
                        {
                            "subject": entity_map[subject_norm]["text"],
                            "predicate": predicate,
                            "object": entity_map[object_norm]["text"],
                            "confidence": 0.80,
                            "extractor": "rules",
                            "evidence": sentence,
                        }
                    )

        return relations

    # ----------------------------------------
    # LLM (fallback seguro)
    # ----------------------------------------

    def extract_llm(self, entities, text):
        if not self.client:
            return []

        entity_names = [e["text"] for e in entities if "text" in e]

        prompt = f"""
Extrae relaciones SOLO entre las entidades listadas.

ENTIDADES:
{json.dumps(entity_names, ensure_ascii=False, indent=2)}

TEXTO:
\"\"\"
{text}
\"\"\"

Usa únicamente estos predicados si aplican:
- locatedIn
- partOf
- hasEvent
- near
- offers
- belongsToCategory

Devuelve EXCLUSIVAMENTE JSON válido con este formato:
[
  {{
    "subject": "A",
    "predicate": "locatedIn",
    "object": "B",
    "confidence": 0.72,
    "evidence": "frase exacta o fragmento"
  }}
]

Reglas:
- No inventes entidades.
- El subject y el object deben estar en la lista de entidades.
- Si no hay relaciones claras, devuelve [].
"""

        try:
            response = self.client.responses.create(
                model="gpt-4.1-mini",
                input=prompt,
            )

            raw_text = response.output_text.strip()

            # limpiar posibles fences ```json
            raw_text = re.sub(r"^```json\s*", "", raw_text)
            raw_text = re.sub(r"^```\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)

            data = json.loads(raw_text)

            if not isinstance(data, list):
                return []

            entity_map = self._entity_map(entities)
            cleaned = []

            for item in data:
                if not isinstance(item, dict):
                    continue

                subject = item.get("subject")
                predicate = item.get("predicate")
                obj = item.get("object")
                confidence = item.get("confidence", 0.60)
                evidence = item.get("evidence", "")

                if not subject or not predicate or not obj:
                    continue

                if self._normalize(subject) not in entity_map:
                    continue

                if self._normalize(obj) not in entity_map:
                    continue

                cleaned.append(
                    {
                        "subject": entity_map[self._normalize(subject)]["text"],
                        "predicate": predicate,
                        "object": entity_map[self._normalize(obj)]["text"],
                        "confidence": float(confidence),
                        "extractor": "llm",
                        "evidence": evidence,
                    }
                )

            return cleaned

        except Exception as e:
            print(f"  [WARN] Error en extracción LLM de relaciones: {e}")
            return []

    # ----------------------------------------
    # MÉTODO PRINCIPAL
    # ----------------------------------------

    def extract(self, entities, text):
        relations = []

        # primero reglas
        relations.extend(self.extract_rules(entities, text))

        # fallback LLM solo si no hubo nada por reglas
        if len(relations) == 0:
            relations.extend(self.extract_llm(entities, text))

        return relations