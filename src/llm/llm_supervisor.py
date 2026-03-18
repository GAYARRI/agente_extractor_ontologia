import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class LLMSupervisor:

    def __init__(self):

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("❌ OPENAI_API_KEY no encontrada")

        self.client = OpenAI(api_key=api_key)

    def analyze_entities(self, entities, text):

        prompt = f"""
Eres un experto en turismo y ontologías.

Analiza estas entidades extraídas de un texto turístico.

Tareas:
1. Elimina duplicados o entidades incorrectas
2. Asigna la mejor clase ontológica:
   Island, Beach, City, Municipality, Festival, NaturalArea, Valley, Ocean, Marina, Place, ReligiousEvent
3. Asigna un score (0-1)
4. Genera:
   - descripción corta (máx 15 palabras)
   - descripción larga (máx 40 palabras)

Texto:
{text}

Entidades:
{entities}

Devuelve JSON:
[
  {{
    "entity": "...",
    "class": "...",
    "score": 0.95,
    "short_description": "...",
    "long_description": "..."
  }}
]
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )

            content = response.choices[0].message.content

            import json
            return json.loads(content)

        except Exception as e:
            print("LLM supervisor error:", e)
            return []