class ImageEnricher:

    def enrich(self, entity, text):

        props = {}

        t = text.lower()

        # 🔥 más robusto
        if any(x in t for x in ["playa", "arena", "mar"]):
            props["visualType"] = "Beach"
            props["image"] = "https://upload.wikimedia.org/wikipedia/commons/9/9e/Playa_Maspalomas.jpg"

        elif any(x in t for x in ["faro"]):
            props["visualType"] = "Lighthouse"
            props["image"] = "https://upload.wikimedia.org/wikipedia/commons/3/3e/Faro_de_Maspalomas.jpg"

        elif any(x in t for x in ["dunas"]):
            props["visualType"] = "Dunes"
            props["image"] = "https://upload.wikimedia.org/wikipedia/commons/0/02/Dunas_Maspalomas.jpg"

        return props