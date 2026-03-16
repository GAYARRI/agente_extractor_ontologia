import re


class TourismEntityExtractor:

    def __init__(self):

        # -------------------------
        # eventos turísticos
        # -------------------------

        self.event_patterns = [
            r"Fiesta de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
            r"Romería de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
            r"Semana Santa",
            r"Feria de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
            r"Festival de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
            r"Carnaval de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+"
        ]

        # -------------------------
        # keywords de POI
        # -------------------------

        self.poi_keywords = [
            "Playa",
            "Castillo",
            "Museo",
            "Iglesia",
            "Parque",
            "Observatorio",
            "Ruta",
            "Puerto",
            "Mirador",
            "Cueva",
            "Faro",
            "Laguna"
        ]

        # palabras basura frecuentes en NER
        self.bad_words = {
            "Ideal",
            "Turísticos",
            "Turisticos",
            "Únicos",
            "Unicos"
        }


    def tokenize(self, text):

        words = text.split()

        cleaned = []

        for w in words:

            w = re.sub(r"[^\wáéíóúÁÉÍÓÚñÑ]", "", w)

            if not w:
                continue

            cleaned.append(w)

        return cleaned


    def extract(self, text):

        entities = []

        # -------------------------
        # 1️⃣ detectar eventos
        # -------------------------

        for pattern in self.event_patterns:

            matches = re.findall(pattern, text)

            for m in matches:
                entities.append(m.strip())


        # -------------------------
        # 2️⃣ tokenizar texto
        # -------------------------

        words = self.tokenize(text)


        # -------------------------
        # 3️⃣ detectar bigramas
        # -------------------------

        for i in range(len(words) - 1):

            w1 = words[i]
            w2 = words[i + 1]

            if w1.istitle() and w2.istitle():

                if w2 in self.bad_words:
                    continue

                candidate = f"{w1} {w2}"

                entities.append(candidate)


        # -------------------------
        # 4️⃣ detectar trigramas
        # -------------------------

        for i in range(len(words) - 2):

            w1 = words[i]
            w2 = words[i + 1]
            w3 = words[i + 2]

            if w1.istitle() and w2.istitle() and w3.istitle():

                if w3 in self.bad_words:
                    continue

                candidate = f"{w1} {w2} {w3}"

                entities.append(candidate)


        # -------------------------
        # 5️⃣ detectar POIs
        # -------------------------

        for keyword in self.poi_keywords:

            matches = re.findall(
                rf"{keyword} de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
                text
            )

            for m in matches:
                entities.append(m.strip())


        # -------------------------
        # 6️⃣ caso especial
        # -------------------------

        if "fuga de la diabla" in text.lower():
            entities.append("La Fuga de la Diabla")


        # -------------------------
        # eliminar duplicados
        # -------------------------

        entities = list(set(entities))

        return entities