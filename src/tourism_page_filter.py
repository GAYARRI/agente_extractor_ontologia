import re


class TourismPageFilter:

    def __init__(self):

        # palabras que indican contenido turístico
        self.tourism_keywords = [
            "museo",
            "monumento",
            "catedral",
            "iglesia",
            "palacio",
            "castillo",
            "parque",
            "ruta",
            "sendero",
            "playa",
            "hotel",
            "restaurante",
            "gastronom",
            "evento",
            "festival",
            "turismo",
            "atracción",
            "visitar",
            "patrimonio",
            "histórico"
        ]

        # páginas que NO queremos
        self.blocked_patterns = [
            "cookie",
            "privacidad",
            "privacy",
            "login",
            "signin",
            "account",
            "newsletter",
            "contact",
            "legal",
            "terms",
            "policy",
            "gdpr"
        ]


    def is_tourism_page(self, url, text):

        url = url.lower()
        text = text.lower()

        # bloquear páginas no útiles
        for pattern in self.blocked_patterns:
            if pattern in url:
                return False

        # detectar contenido turístico
        score = 0

        for keyword in self.tourism_keywords:
            if keyword in text:
                score += 1

        return score >= 2