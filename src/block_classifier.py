class BlockClassifier:

    def __init__(self, entity_extractor, matcher):

        self.extractor = entity_extractor
        self.matcher = matcher


    def classify(self, block):

        text = block.get("text")

        if not text:
            return None

        entities = self.extractor.extract(text)

        if not entities:
            return None

        results = []

        for entity in entities:

            # 🔵 CONTEXTO SEMÁNTICO
            context = f"{entity} {text}"

            match = self.matcher.match(context)

            if not match:
                continue

            results.append({
                "entity": entity,
                "class": match["label"],
                "uri": match["uri"],
                "score": match["score"]
            })

        if not results:
            return None

        return {
            "text": text,
            "entities": results
        }