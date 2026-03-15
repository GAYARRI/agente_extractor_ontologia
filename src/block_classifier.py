from src.tourism_entity_extractor import TourismEntityExtractor


class BlockClassifier:

    def __init__(self):

        self.entity_extractor = TourismEntityExtractor()


    def classify(self, block):

        text = block.get("text", "")
        image = block.get("image", None)

        if not text:
            return None

        entity_candidates = self.entity_extractor.extract(text)

        if not entity_candidates:
            return None

        return {
            "entities": entity_candidates,
            "description": text,
            "image": image
        }