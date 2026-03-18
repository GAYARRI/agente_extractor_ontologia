from openai import OpenAI


class LLMClient:

    def __init__(self):
        self.client = OpenAI()

    # ==================================================
    # CLASIFICACIÓN ONTOLÓGICA
    # ==================================================

    def classify_entity(self, entity, context):

        prompt = f"""
Eres un experto en turismo y ontologías.

Clasifica la siguiente entidad en una de estas clases:

Island, Beach, City, Municipality, Festival, NaturalArea, Valley, Ocean, Marina, Place

Entidad: {entity}
Contexto: {context}

Devuelve SOLO el nombre de la clase.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print("LLM classification error:", e)
            return None

    # ==================================================
    # DESCRIPCIONES
    # ==================================================

    def generate_descriptions(self, entity, text):

        prompt = f"""
Genera dos descripciones para una entidad turística:

Entidad: {entity}
Texto: {text}

1. Descripción corta (máximo 15 palabras)
2. Descripción larga (máximo 40 palabras)

Formato:
SHORT: ...
LONG: ...
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )

            content = response.choices[0].message.content

            short = ""
            long = ""

            for line in content.split("\n"):
                if line.startswith("SHORT:"):
                    short = line.replace("SHORT:", "").strip()
                elif line.startswith("LONG:"):
                    long = line.replace("LONG:", "").strip()

            return short, long

        except Exception as e:
            print("LLM description error:", e)
            return "", ""