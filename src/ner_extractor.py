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
            r"\b[Pp]laya\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Dd]unas\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Ff]aro\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Pp]uerto\s+deportivo\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Pp]uertos?\s+deportivos?\b",
            r"\b[Pp]arque\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Pp]alacio\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Mm]useo\s+(?:del|de la|de los|de las|de)?\s*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Rr]estaurante\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Hh]otel\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Bb]arranco\s+de\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
            r"\b[Ll]ago\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚñÑ\-]+)*\b",
        ]

        self.invalid_exact = {
            "inicio",
            "contacto",
            "cookies",
            "buscar",
            "mapa",
            "sur",
            "gran",
            "tranquila",
        }

    def _normalize_spaces(self, text: str) -> str:
        return " ".join(text.strip().split())

    def _clean_entity_text(self, text: str) -> str:
        text = self._normalize_spaces(text)

        # limpiar puntuación periférica
        text = text.strip(" ,;:()[]{}\"'")

        # quitar duplicados accidentales de espacios
        text = re.sub(r"\s+", " ", text)

        return text

    def _is_valid_candidate(self, text: str) -> bool:
        if not text:
            return False

        clean = text.strip().lower()

        if len(clean) < 3:
            return False

        if clean in self.invalid_exact:
            return False

        # evitar entidades solo numéricas
        if re.fullmatch(r"[\d\W_]+", clean):
            return False

        return True

    def extract_stanza_entities(self, text):
        doc = self.nlp(text)
        entities = []

        for sentence in doc.sentences:
            for ent in sentence.ents:
                if ent.type not in self.allowed_labels:
                    continue

                entity_text = self._clean_entity_text(ent.text)

                if not self._is_valid_candidate(entity_text):
                    continue

                entities.append({
                    "text": entity_text,
                    "normalized_text": entity_text,
                    "source": "stanza",
                    "ner_label": ent.type,
                    "confidence": None,
                })

        return entities

    def extract_heuristic_entities(self, text):
        entities = []

        for pattern in self.tourism_patterns:
            for match in re.finditer(pattern, text):
                entity_text = self._clean_entity_text(match.group(0))

                if not self._is_valid_candidate(entity_text):
                    continue

                entities.append({
                    "text": entity_text,
                    "normalized_text": entity_text,
                    "source": "heuristic",
                    "ner_label": "TOURISM_CANDIDATE",
                    "confidence": None,
                })

        return entities

    def merge_entities(self, entities):
        merged = {}
        protected_prefixes = (
            "playa de",
            "dunas de",
            "faro de",
            "puerto deportivo",
            "parque ",
            "palacio de",
            "museo ",
            "hotel ",
            "restaurante ",
            "barranco de",
        )

        # prioridad a entidades más largas y heurísticas bien formadas
        entities_sorted = sorted(
            entities,
            key=lambda e: (
                len(e["text"].split()),
                len(e["text"]),
                1 if e.get("source") == "heuristic" else 0,
            ),
            reverse=True,
        )

        for ent in entities_sorted:
            text = ent["text"]
            key = text.lower()

            # si ya existe exacta, saltar
            if key in merged:
                continue

            # evitar que entre una subentidad si ya hay una entidad compuesta mayor
            is_subentity = False
            for existing_key, existing in merged.items():
                existing_text = existing["text"].lower()

                if key == existing_key:
                    is_subentity = True
                    break

                if key in existing_text and existing_text.startswith(protected_prefixes):
                    is_subentity = True
                    break

            if is_subentity:
                continue

            merged[key] = ent

        return list(merged.values())

    def extract(self, text):
        stanza_entities = self.extract_stanza_entities(text)
        heuristic_entities = self.extract_heuristic_entities(text)

        all_entities = stanza_entities + heuristic_entities
        return self.merge_entities(all_entities)
    
    def extract_from_block(self, block):
        text = block.get("text", "")
        entities = self.extract(text)
        enriched = []
        for ent in entities:
            if isinstance(ent, dict):
                item = dict(ent)
                item["block_id"] = block.get("block_id")
                item["block_heading"] = block.get("heading", "")
                item["block_image"] = block.get("image")
                item["page_url"] = block.get("page_url", "")
                enriched.append(item)
            else:
                enriched.append({
                    "text": str(ent),
                    "block_id": block.get("block_id"),
                    "block_heading": block.get("heading", ""),
                    "block_image": block.get("image"),
                    "page_url": block.get("page_url", ""),
                })

        return enriched
    