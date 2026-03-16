EVENT_KEYWORDS = [
    "Carnaval",
    "Semana Santa",
    "Festival",
    "Romería",
    "Fiesta",
    "Feria"
]


class EventDetector:

    def detect(self, entity):

        for word in EVENT_KEYWORDS:

            if word.lower() in entity.lower():

                return {
                    "type": "Event",
                    "label": entity
                }

        return None