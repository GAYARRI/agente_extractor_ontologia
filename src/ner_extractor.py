import re
import stanza


class NERExtractor:
    def __init__(self, allowed_labels=None):
        self.nlp = stanza.Pipeline(
            lang="es",
            processors="tokenize,ner",
            use_gpu=False
        )

        self.allowed_labels = allowed_labels or {"LOC", "ORG", "MISC", "PER"}

        self.tourism_patterns = [
            r"\b[Mm]useo(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)*(?:\s+del\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)?\b",
            r"\b[Pp]arque(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)+\b",
            r"\b[Pp]alacio\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+(?:\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)?\b",
            r"\b[Pp]uerta\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+\b",
            r"\b[Pp]laza\s+(?:de\s+)?[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)*\b",
            r"\b[Tt]eatro\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)*\b",
            r"\b[Hh]otel\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)*\b",
            r"\b[Rr]estaurante\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)*\b",
            r"\b[Mm]ercado\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)*\b",
            r"\b[Cc]atedral\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)*\b",
            r"\b[Bb]asílica\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑñ\-]+)*\b",
            
        ]

    def _normalize(self, text: str) -> str:
        return " ".join(text.strip().split())

    def extract_stanza_entities(self, text):
        doc = self.nlp(text)
        entities = []

        for sentence in doc.sentences:
            for ent in sentence.ents:
                if ent.type not in self.allowed_labels:
                    continue

                entity_text = self._normalize(ent.text)

                if len(entity_text) < 3:
                    continue

                entities.append({
                    "text": entity_text,
                    "source": "stanza",
                    "ner_label": ent.type,
                    "confidence": None
                })

        return entities

    def extract_heuristic_entities(self, text):
        entities = []

        for pattern in self.tourism_patterns:
            for match in re.finditer(pattern, text):
                entity_text = self._normalize(match.group(0))

                if len(entity_text) < 3:
                    continue

                entities.append({
                    "text": entity_text,
                    "source": "heuristic",
                    "ner_label": "TOURISM_CANDIDATE",
                    "confidence": None
                })

        return entities

    def merge_entities(self, entities):
        merged = []
        seen = set()

        for ent in entities:
            key = ent["text"].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(ent)

        return merged

    def extract(self, text):
        stanza_entities = self.extract_stanza_entities(text)
        heuristic_entities = self.extract_heuristic_entities(text)

        all_entities = stanza_entities + heuristic_entities
        return self.merge_entities(all_entities)