import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv


class LLMSupervisor:

    def __init__(self, ontology_index=None):

        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("❌ OPENAI_API_KEY no encontrada")

        self.client = OpenAI(api_key=api_key)
        self.ontology_index = ontology_index

    # ==================================================
    # SAFE JSON
    # ==================================================

    def safe_json_parse(self, text):

        if not text:
            return []

        try:
            return json.loads(text)
        except:
            pass

        try:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass

        print("⚠️ JSON inválido del LLM:")
        print(text)

        return []

    # ==================================================
    # 🔥 OBTENER CLASES DE LA ONTOLOGÍA
    # ==================================================

    def get_ontology_classes(self):

        if not self.ontology_index:
            return []

        try:
            classes = self.ontology_index.get_all_classes()
            return [c["label"] for c in classes]
        except:
            return []

    # ==================================================
    # 🔥 EXTRACCIÓN GUIADA POR ONTOLOGÍA
    # ==================================================

    def extract_entities(self, text):

        classes = self.get_ontology_classes()

        classes_str = ", ".join(classes[:30])  # limitar para no saturar

        prompt = f"""
Eres un experto en turismo y ontologías.

Extrae entidades del texto usando estas clases ontológicas como referencia:

{classes_str}

Extrae SOLO entidades relevantes que encajen en esas clases.

Texto:
{text}

Devuelve JSON:
["Entidad 1", "Entidad 2"]
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            content = response.choices[0].message.content.strip()

            return self.safe_json_parse(content)

        except Exception as e:
            print("LLM extract error:", e)
            return []

    # ==================================================
    # 🔥 CLASIFICACIÓN USANDO ONTOLOGÍA
    # ==================================================

    def analyze_entities(self, entities, text):

        if not entities:
            return []

        classes = self.get_ontology_classes()
        classes_str = ", ".join(classes[:40])

        prompt = f"""
Eres un experto en turismo y ontologías.

Clasifica las entidades usando EXCLUSIVAMENTE estas clases:

{classes_str}

Tareas:
- eliminar duplicados
- asignar clase ontológica correcta
- score (0-1)
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

            content = response.choices[0].message.content.strip()

            return self.safe_json_parse(content)

        except Exception as e:
            print("LLM analyze error:", e)
            return []