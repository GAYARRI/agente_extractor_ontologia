DESTINATION_KEYWORDS = [
    "Badajoz",
    "Jerez de los Caballeros",
    "Valverde de Leganés",
    "Castilblanco",
    "Herrera del Duque",
    "Magacela",
    "Fuentes de León"
]


class DestinationDetector:

    def detect(self, entity):

        for d in DESTINATION_KEYWORDS:

            if d.lower() in entity.lower():

                return {
                    "type": "Destination",
                    "label": d
                }

        return None