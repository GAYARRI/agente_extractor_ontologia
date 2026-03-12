import re
import os
from openai import OpenAI


class RelationExtractor:

    def __init__(self, properties=None):

        self.properties = properties if properties else []

        api_key = os.getenv("OPENAI_API_KEY")

        self.client = OpenAI(api_key=api_key) if api_key else None

        # reglas simples de relaciones
        self.patterns = [

            ("locatedIn", r"(.+) se encuentra en (.+)"),
            ("locatedIn", r"(.+) está en (.+)"),
            ("locatedIn", r"(.+) ubicado en (.+)"),

            ("partOf", r"(.+) forma parte de (.+)"),

            ("hasEvent", r"(.+) celebra (.+)")
        ]


    # ----------------------------------------
    # REGLAS
    # ----------------------------------------

    def extract_rules(self, text):

        relations = []

        sentences = text.split(".")

        for sentence in sentences:

            for predicate, pattern in self.patterns:

                match = re.search(pattern, sentence, re.IGNORECASE)

                if match:

                    subject = match.group(1).strip()
                    obj = match.group(2).strip()

                    relations.append({
                        "subject": subject,
                        "predicate": predicate,
                        "object": obj
                    })

        return relations


    # ----------------------------------------
    # LLM (fallback)
    # ----------------------------------------

    def extract_llm(self, text, entities):

        if not self.client:
            return []

        prompt = f"""
Extrae relaciones entre estas entidades:

ENTIDADES:
{entities}

TEXTO:
{text}

Devuelve JSON:

[
{{"subject":"A","predicate":"locatedIn","object":"B"}}
]
"""

        try:

            response = self.client.responses.create(
                model="gpt-4.1-mini",
                input=prompt
            )

            return eval(response.output_text)

        except Exception:

            return []


    # ----------------------------------------
    # MÉTODO PRINCIPAL
    # ----------------------------------------

    def extract(self, text, entities):

        relations = []

        relations += self.extract_rules(text)

        if len(relations) == 0:

            relations += self.extract_llm(text, entities)

        return relations