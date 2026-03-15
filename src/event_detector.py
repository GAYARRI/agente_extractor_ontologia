EVENT_WORDS = [
    "Carnaval",
    "Semana Santa",
    "Festival",
    "Romería",
    "Fiesta",
    "Feria"
]


class EventDetector:

    def detect(self, text):

        events = []

        for word in EVENT_WORDS:

            if word in text:
                events.append(word)

        return events