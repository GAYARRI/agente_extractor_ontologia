import re

CONNECTORS = {"de", "del", "la", "las", "los", "y", "e"}

MAX_WORDS = 6


class TourismEntityExtractor:

    def extract(self, text):

        tokens = text.split()

        entities = []
        current = []

        for token in tokens:

            word = token.strip(".,;:!?")

            if not word:
                continue

            if word[0].isupper():

                current.append(word)

            elif word.lower() in CONNECTORS and current:

                current.append(word)

            else:

                if len(current) >= 2:

                    entity = " ".join(current)

                    if len(entity.split()) <= MAX_WORDS:
                        entities.append(entity)

                current = []

        if len(current) >= 2:

            entity = " ".join(current)

            if len(entity.split()) <= MAX_WORDS:
                entities.append(entity)

        return list(set(entities))