import stanza
stanza.download('es')

class NERDetector:

    def __init__(self):

        self.nlp = stanza.Pipeline(
            lang="es",
            processors="tokenize,ner"
        )

    def extract_entities(self, text):

        doc = self.nlp(text)

        entities = []

        for sentence in doc.sentences:
            for ent in sentence.ents:

                if ent.type in ["LOC","ORG","MISC"]:

                    entities.append(ent.text)

        return list(set(entities))