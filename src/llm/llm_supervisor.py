import json
import re
from openai import OpenAI


class LLMSupervisor:
    def __init__(self, ontology_index, model="gpt-4o-mini"):
        self.ontology_index = ontology_index
        self.model = model
        try:
            self.client = OpenAI()
        except Exception as e:
            print("⚠️ LLM no disponible:", e)
            self.client = None


    # ==================================================
    # JSON SAFE PARSE
    # ==================================================

    def safe_json_parse(self, content):
        if not content:
            return []

        content = content.strip()

        # quitar fences markdown si vienen
        content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"^```\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        try:
            return json.loads(content)
        except Exception:
            pass

        # intentar rescatar primer bloque JSON
        match = re.search(r"(\{.*\}|\[.*\])", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        return []

    # ==================================================
    # ONTOLOGY CONTEXT
    # ==================================================

    def build_ontology_context(self, max_classes=80):
        """
        Intenta construir un contexto textual de clases ontológicas
        a partir de ontology_index sin asumir demasiado de su implementación.
        """
        class_lines = []

        # Caso 1: diccionario tipo {class_name: description}
        if hasattr(self.ontology_index, "classes"):
            classes_obj = getattr(self.ontology_index, "classes")

            if isinstance(classes_obj, dict):
                for i, (cls, desc) in enumerate(classes_obj.items()):
                    if i >= max_classes:
                        break
                    class_lines.append(f"- {cls}: {desc}")

            elif isinstance(classes_obj, list):
                for i, item in enumerate(classes_obj):
                    if i >= max_classes:
                        break
                    class_lines.append(f"- {item}")

        # Caso 2: método get_all_classes()
        elif hasattr(self.ontology_index, "get_all_classes"):
            try:
                all_classes = self.ontology_index.get_all_classes()
                for i, item in enumerate(all_classes):
                    if i >= max_classes:
                        break
                    class_lines.append(f"- {item}")
            except Exception:
                pass

        # fallback mínimo
        if not class_lines:
            class_lines = [
                "- Place: lugar físico, destino, ciudad, barrio, zona o recurso visitable",
                "- TouristAttraction: atracción turística, monumento, museo, punto de interés",
                "- Accommodation: hotel, hostal, apartamento turístico, camping",
                "- Restaurant: restaurante, bar, cafetería, local gastronómico",
                "- Event: evento concreto, festival, feria, concierto, exposición",
                "- TransportInfrastructure: aeropuerto, estación, terminal, muelle",
                "- Organization: institución, organismo, oficina de turismo, ayuntamiento",
                "- LocalBusiness: empresa o servicio turístico identificable",
                "- Route: ruta, itinerario o recorrido turístico concreto",
                "- Service: servicio concreto útil para el turista",
            ]

        return "\n".join(class_lines)

    # ==================================================
    # PROMPTS
    # ==================================================

    def build_extraction_prompt(self, text):

        return f"""

Eres un agente de turismo experto en extracción de instancias de un website que se te proporciona.

Tu tarea es extraer ÚNICAMENTE instancias del website porporcionado.
MUY IMPORTANTE : SOLO ACEPTAR URLS DEL DOMINIO INICIAL PROPORCIONADO DONDE SE CUMPLA QUE  HOSTNAME == DOMINIO_INICIAL

DEFINICIÓN DE INSTANCIA DE TURISMO:
Una instancia es un elemento del mundo real, concreto, identificable y relevante para el turismo, que puede ser visitado, utilizado, experimentado o consultado por un turista.

EJEMPLOS VÁLIDOS:
- ciudades, barrios, lugares y destinos
- monumentos, museos, parques, plazas, playas
- aeropuertos, estaciones, terminales, muelles
- hoteles, restaurantes, empresas turísticas
- eventos concretos con identidad propia
- instituciones u organizaciones estrechamente relacionadas con el turismo

NO EXTRAIGAS:
- categorías o secciones del site: cultura, ocio, monumentos, museos, agenda
- actividades genéricas: eventos deportivos, actividades en familia o planes que no esten inequívocamente relacionados con el hecho turístico
- conceptos abstractos: gastronomía, patrimonio, tradición, folklore
- fragmentos de direcciónes: A-4 Km, 41020 Sevilla, Av. de Kansas City
- números, códigos, teléfonos, horarios
- elementos de navegación web: ver listado, haz clic aquí, ir a página
- frases cortadas o concatenaciones artificiales: Museos De, Salir La, Cultura Artesanía Fiestas
- servicios genéricos sin nombre propio: taxi, autobús, metro, líneas de autobús
- términos demasiado genéricos que no designen una instancia concreta 

REGLAS:
- Extrae solo fragmentos de texto relacionables con el turismo . 
- No inventes instancias que no estén previamente presentes en el texto del website proporcionado.
- No unas palabras que no formen una instancia real del texto del dominio inicial.
- Prioriza instancias inequivocamente relacionadas con el turismo, con nombre propio o identidad concreta.
- Si una expresión es dudosa y no parece encajar en el fenómeno turístico, NO la extraigas.
- Si no hay entidades válidas, devuelve lista vacía.

TEXTO:
\"\"\"
{text}
\"\"\"

FORMATO DE SALIDA:
Devuelve SOLO un JSON válido con esta forma:
{{
  "entities": ["Entidad 1", "Entidad 2"]
}}
""".strip()

    def build_validation_prompt(self, entities, text):
        entities_json = json.dumps(entities, ensure_ascii=False)

        return f"""

Eres un validador de instanias asociadas al turismo.

Tu tarea es extraer de una lista de instancias, SOLO las que sean susceptibles de ser clasificables en alguna de las entidades turísticas proporcionadas, concretas e identificables.

CRITERIO DE ACEPTACIÓN:
Una instancia acabará siendo instancia candidata si es una instancia del mundo real indubitablemente relevante para el turismo, con identidad propia. 

ELIMINA:
- categorías
- conceptos abstractos
- actividades genéricas
- fragmentos de dirección
- números, códigos, teléfonos
- texto cortado
- concatenaciones artificiales
- duplicados
- expresiones demasiado genéricas sin identidad propia

MANTÉN:
- topónimos
- monumentos
- museos
- infraestructuras de transporte
- negocios identificables que pueden estar involucrados en la acividad turística
- instituciones asociadas al negocio turístico
- eventos de interés turísticos concretos
- puntos de interés turísitico con nombre reconocible

CONTEXTO:
\"\"\"
{text}
\"\"\"

ENTIDADES CANDIDATAS:
{entities_json}

FORMATO DE SALIDA:
Devuelve SOLO un JSON válido con esta forma:
{{
  "entities": ["Entidad válida 1", "Entidad válida 2"]
}}
""".strip()

    def build_classification_prompt(self, entities, text):
        entities_json = json.dumps(entities, ensure_ascii=False)
        ontology_context = self.build_ontology_context()

        return f"""

Eres un sistema experto en clasificación ontológica de instancias turísticas.

Se te proporciona:
1. Un texto de contexto.
2. Una lista de instancias candidatas, susceptibles de ser clasificadas según una ontología de turismo.
3. Una lista de entidades ontológicas dentro de las cuales se clasificarán las instancias candidatas.


DEFINICIÓN:
Una entidad ontológica de turismo es un elemento identificable relevante para el turista y enmarcado en el hecho turístico.

TU TAREA:
Clasificar cada instancia candidata en la entidad ontológica más adecuada, usando el contexto y las lista de entidades disponibles.

REGLAS IMPORTANTES:
- NO inventes nuevas entidades.
- NO cambies el nombre de las entidades.
- NO clasifiques categorías, conceptos o fragmentos.
- Si una entidad no es realmente válida, descártala.
- Si hay duda razonable entre varias, usa la entidad más general que encaje.
- No dejes sin clasificar ninguna entidad válida.

ONTOLOGÍA TURÍSICA:
{ontology_context}

GUÍA GENERAL:
- Place: lugar físico, ciudad, barrio, zona, enclave
- TouristAttraction: monumento, museo, atracción, recurso visitable
- Accommodation: hotel, hostal, apartamento turístico, camping
- Restaurant: restaurante, bar, cafetería, local gastronómico
- Event: evento concreto, feria, festival, concierto, exposición
- TransportInfrastructure: aeropuerto, estación, terminal, muelle
- Organization: institución, organismo, ayuntamiento, oficina de turismo
- LocalBusiness: empresa o servicio identificable
- Route: ruta o itinerario concreto
- Service: servicio útil concreto para turistas

TEXTO:
\"\"\"
{text}
\"\"\"

ENTIDADES:
{entities_json}

FORMATO DE SALIDA:
Devuelve SOLO un JSON válido con esta forma:
{{
  "entities": [
    {{
      "entity": "Nombre exacto de la entidad",
      "class": "ClaseOntologica",
      "score": 0.0,
      "short_description": "Descripción breve y concreta",
      "long_description": "Descripción algo más amplia y contextual"
    }}
  ]
}}

RESTRICCIONES:
- score debe estar entre 0 y 1
- short_description máximo 160 caracteres
- long_description máximo 400 caracteres
""".strip()

    # ==================================================
    # LOW LEVEL CALL
    # ==================================================

    def call_llm_json(self, prompt, default=None):
        if default is None:
            default = []

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            content = response.choices[0].message.content.strip()
            

            return  self.safe_json_parse(content)

        except Exception as e:
            print("LLM extract error:", e)
            return []

    # ==================================================
    # PUBLIC API
    # ==================================================

    def extract_entities(self, text):
        prompt = self.build_extraction_prompt(text)
        data = self.call_llm_json(prompt, default={"entities": []})

        if isinstance(data, dict):
            entities = data.get("entities", [])
            if isinstance(entities, list):
                return [str(e).strip() for e in entities if str(e).strip()]

        return []

    def validate_entities(self, entities, text):
        if not entities:
            return []

        prompt = self.build_validation_prompt(entities, text)
        data = self.call_llm_json(prompt, default={"entities": []})

        if isinstance(data, dict):
            clean_entities = data.get("entities", [])
            if isinstance(clean_entities, list):
                return [str(e).strip() for e in clean_entities if str(e).strip()]

        return []

    def analyze_entities(self, entities, text):
        if not entities:
            return []

        prompt = self.build_classification_prompt(entities, text)
        data = self.call_llm_json(prompt, default={"entities": []})

        if isinstance(data, dict):
            items = data.get("entities", [])
            if isinstance(items, list):
                clean_items = []

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    entity = str(item.get("entity", "")).strip()
                    entity_class = str(item.get("class", "Place")).strip() or "Place"

                    try:
                        score = float(item.get("score", 0.5))
                    except Exception:
                        score = 0.5

                    score = max(0.0, min(1.0, score))

                    short_description = str(item.get("short_description", "")).strip()
                    long_description = str(item.get("long_description", "")).strip()

                    if not entity:
                        continue

                    clean_items.append({
                        "entity": entity,
                        "class": entity_class,
                        "score": score,
                        "short_description": short_description[:160],
                        "long_description": long_description[:400],
                    })

                return clean_items

        return []

    # ==================================================
    # FULL PIPELINE
    # ==================================================

    def extract_and_validate_entities(self, text):
        extracted = self.extract_entities(text)
        validated = self.validate_entities(extracted, text)
        return validated