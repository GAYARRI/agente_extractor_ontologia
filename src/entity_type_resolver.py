import re


class EntityTypeResolver:

    def __init__(self):

        self.rules = {

            "Beach": [
                "playa"
            ],

            "Trail": [
                "camino",
                "sendero",
                "ruta"
            ],

            "Activity": [
                "surf",
                "buceo",
                "submarinismo",
                "senderismo",
                "pesca",
                "deportes"
            ],

            "Event": [
                "festival",
                "carnaval",
                "evento"
            ],

            "Hotel": [
                "hotel",
                "resort"
            ],

            "NaturalArea": [
                "barranco",
                "parque",
                "dunas",
                "montaña"
            ],

            "Municipality": [
                "ayuntamiento",
                "municipio"
            ],

            "Island": [
                "canaria",
                "isla"
            ]
        }


    def resolve(self, mention, context="", block_text=""):

        text = f"{mention} {context} {block_text}".lower()

        for cls, keywords in self.rules.items():

            for k in keywords:

                if k in text:

                    return {

                        "class": cls,
                        "confidence": 0.85
                    }

        return {

            "class": "Place",
            "confidence": 0.5
        }