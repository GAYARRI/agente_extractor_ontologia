import re


class TourismOntologyAutoExpander:

    def __init__(self):

        # patrones típicos del turismo
        self.patterns = [

            ("Route", r"Ruta de ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)"),

            ("Festival", r"Festival de ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)"),

            ("Event", r"(Carnaval|Fiesta|Romería) de ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)"),

            ("Beach", r"Playa de ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)"),

            ("NaturalSite", r"Parque Natural de ([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)")
        ]


    def discover_classes(self, text):

        new_classes = []

        for base_class, pattern in self.patterns:

            matches = re.findall(pattern, text)

            for m in matches:

                if isinstance(m, tuple):
                    name = m[-1]
                else:
                    name = m

                candidate_class = f"{name}{base_class}"

                new_classes.append(candidate_class)

        return new_classes