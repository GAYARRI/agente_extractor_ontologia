from src.tourism_entity_extractor import TourismEntityExtractor


class BlockClassifier:

    def __init__(self, matcher):
        """
        matcher: OntologyMatcher
        """
        self.matcher = matcher
        self.extractor = TourismEntityExtractor()


    def classify(self, block):

        text = block.get("text")

        if not text:
            return None

        # extraer entidades del texto
        entities = self.extractor.extract(text)

        if not entities:
            return {
                "text": text,
                "entities": []
            }

        results = []

        for entity in entities:

            match = self.matcher.match(entity)

            if not match:
                continue

            results.append({
                "entity": entity,
                "class": match["label"],
                "uri": match["uri"],
                "score": match["score"]
            })

        return {
            "text": text,
            "entities": results
        }