import re


class EventDetector:

    patterns = [
        r"Fiesta de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
        r"Romería de [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+",
        r"Semana Santa"
    ]

    def detect(self, text):

        events = []

        for p in self.patterns:

            matches = re.findall(p, text)

            events.extend(matches)

        return events