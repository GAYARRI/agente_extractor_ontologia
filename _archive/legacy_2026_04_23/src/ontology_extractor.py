import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from src.utils.json_utils import safe_load_json

load_dotenv()



class OntologyExtractor:

    def __init__(self, classes):

        self.classes = classes

        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )

    def classify_entities(self, entities):

        if not entities:
            return {"entities": []}

        prompt = f"""
You are an ontology entity classifier.

Given a list of candidate entities extracted from text,
assign the most appropriate ontology class from this list.

Ontology classes:
{self.classes}

Entities:
{entities}

Return JSON only in this format:

{{
 "entities":[
   {{"name":"entity","class":"OntologyClass"}}
 ]
}}
"""

        response = self.client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        result = response.output[0].content[0].text

        try:
            return safe_load_json(result)
        except:
            return {"entities": []}