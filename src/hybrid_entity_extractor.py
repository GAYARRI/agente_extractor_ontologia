import re
import stanza


class HybridEntityExtractor:

    def __init__(self):

        print("Cargando modelo NER...")

        self.nlp = stanza.Pipeline(
            "es",
            processors="tokenize,ner",
            verbose=False
        )

    # --------------------------------
    # 1 NER clásico
    # --------------------------------

    def ner_entities(self, text):

        doc = self.nlp(text)

        entities = []

        for sent in doc.sentences:

            for ent in sent.ents:

                entities.append(ent.text)

        return entities

    # --------------------------------
    # 2 frases capitalizadas
    # --------------------------------

    def capitalized_entities(self, text):

        pattern = r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)'

        matches = re.findall(pattern, text)

        return matches

    # --------------------------------
    # 3 limpieza
    # --------------------------------

    def clean_entities(self, entities):

        cleaned = []

        blacklist = [
            "Inicio",
            "Contacto",
            "Blog",
            "Más",
            "Leer",
            "Este",
            "Oeste",
            "Norte",
            "Sur"
        ]

        for e in entities:

            e = e.strip()

            if len(e) < 3:
                continue

            if e in blacklist:
                continue

            cleaned.append(e)

        return list(set(cleaned))

    # --------------------------------
    # extractor final
    # --------------------------------

    def extract(self, text):

        ner = self.ner_entities(text)

        caps = self.capitalized_entities(text)

        all_entities = ner + caps

        return self.clean_entities(all_entities)