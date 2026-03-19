class ImageEnricher:

    def enrich(self, entity, text):

        e = entity.lower()

        # 🔥 reglas simples pero efectivas
        if "gran canaria" in e:
            return {"image": "https://upload.wikimedia.org/wikipedia/commons/8/8d/Gran_Canaria.jpg"}

        if "atlántico" in e:
            return {"image": "https://upload.wikimedia.org/wikipedia/commons/a/a8/Atlantic_Ocean.jpg"}

        if "valle" in e:
            return {"image": "https://upload.wikimedia.org/wikipedia/commons/3/3c/Valley.jpg"}

        if "carnaval" in e:
            return {"image": "https://upload.wikimedia.org/wikipedia/commons/6/6e/Carnival.jpg"}

        if "pasito blanco" in e:
            return {"image": "https://upload.wikimedia.org/wikipedia/commons/1/1e/Marina.jpg"}

        # fallback inteligente
        if "playa" in text.lower() or "mar" in text.lower():
            return {"image": "https://upload.wikimedia.org/wikipedia/commons/9/9e/Beach.jpg"}

        return {}