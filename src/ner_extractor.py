import stanza


class NERExtractor:

    def __init__(self):

        self.nlp = stanza.Pipeline(
            lang="es",
            processors="tokenize,ner",
            use_gpu=False
        )

    def extract(self, text):

        doc = self.nlp(text)

        entities = set()

        for sentence in doc.sentences:

            for ent in sentence.ents:

                name = ent.text.strip()

                if len(name) < 3:
                    continue

                entities.add(name)

        return list(entities)