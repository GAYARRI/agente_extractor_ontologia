import json
import sys
import re
from openai import OpenAI
from src.ontology.type_normalizer import normalize_type
from src.utils.json_utils import safe_load_json
from src.supervision.gold.examples import (
    load_gold_examples,
    normalize_url,
    candidate_vs_gold_score,
)


class LLMSupervisor:
    def __init__(self, ontology_index, model="gpt-4o-mini", gold_examples_path="benchmark/Ejemplos.csv"):
        self.ontology_index = ontology_index
        self.model = model

        try:
            self.client = OpenAI()
        except Exception as e:
            print("⚠️ LLM no disponible:", e)
            self.client = None

        try:
            self.gold_examples = load_gold_examples(gold_examples_path)
            print(f"[LLM_SUPERVISOR] Golden examples cargados: {len(self.gold_examples)}", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] No se pudieron cargar golden examples: {e}")
            self.gold_examples = {}

    # ==================================================
    # JSON SAFE PARSE
    # ==================================================

    def safe_json_parse(self, content):
        if not content:
            return []

        content = content.strip()

        content = re.sub(r"^```json\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"^```\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

        try:
            return safe_load_json(content)
        except Exception:
            pass

        match = re.search(r"(\{.*\}|\[.*\])", content, re.DOTALL)
        if match:
            try:
                return safe_load_json(match.group(1))
            except Exception:
                pass

        return []

    # ==================================================
    # GOLD PRIOR / GOLD PROMPT
    # ==================================================

    def normalize_llm_class(self, value: str) -> str:
        if not value:
            return ""
        return normalize_type(value)

    def build_gold_example_prompt_context(self, url: str) -> str:
        """
        Si la URL actual existe en el conjunto gold, devuelve un bloque breve
        para orientar la clasificación del LLM.
        """
        if not url:
            return ""

        url_norm = normalize_url(url)
        gold_case = self.gold_examples.get(url_norm)

        if not gold_case:
            return ""

        gold_entity = gold_case.get("entity", "")
        gold_type = gold_case.get("type", "")

        if not gold_entity:
            return ""

        return f"""
EJEMPLO SUPERVISADO RELEVANTE PARA ESTA URL:
- URL: {url_norm}
- Entidad principal esperada: {gold_entity}
- Clase ontológica esperada: {gold_type}

Usa este ejemplo como una señal de priorización.
IMPORTANTE:
- No copies ciegamente el ejemplo.
- Úsalo solo como referencia si encaja con el texto real.
- Si el texto contradice claramente el ejemplo, prioriza el texto.
""".strip()

    def apply_gold_prior(self, url: str, candidates: list[dict]) -> list[dict]:
        url_norm = normalize_url(url)
        gold_case = self.gold_examples.get(url_norm)

        if not gold_case:
            return candidates

        enriched = []
        for cand in candidates:
            if not isinstance(cand, dict):
                continue

            new_cand = dict(cand)
            new_cand["gold_alignment_score"] = candidate_vs_gold_score(cand, gold_case)
            enriched.append(new_cand)

        enriched.sort(
            key=lambda x: (
                x.get("gold_alignment_score", 0.0),
                x.get("score", 0.0),
            ),
            reverse=True,
        )

        print(f"[LLM_SUPERVISOR][GOLD] URL conocida: {url_norm}", file=sys.stderr)
        for cand in enriched[:5]:
            print(
                "[LLM_SUPERVISOR][GOLD] candidate=",
                cand.get("entity") or cand.get("entity_name") or cand.get("name"),
                " class=",
                cand.get("class"),
                " gold_alignment_score=",
                round(cand.get("gold_alignment_score", 0.0), 4)
                if isinstance(cand.get("gold_alignment_score", 0.0), (int, float))
                else cand.get("gold_alignment_score", 0.0),
                " llm_score=",
                cand.get("score", 0.0),
                file=sys.stderr,
            )

        return enriched

    def rerank_classified_entities(self, url: str, items: list[dict]) -> list[dict]:
        """
        Re-rank de entidades ya clasificadas por el LLM.
        """
        if not items:
            return items

        candidates = []
        for item in items:
            if not isinstance(item, dict):
                continue

            candidate = dict(item)
            candidate["entity_name"] = item.get("entity", "")
            candidate["normalized_type"] = item.get("normalized_type", "") or self.normalize_llm_class(item.get("class", ""))
            candidates.append(candidate)

        reranked = self.apply_gold_prior(url, candidates)

        clean_items = []
        for item in reranked:
            clean_items.append({
                "entity": item.get("entity", ""),
                "class": item.get("class", ""),
                "score": item.get("score", 0.5),
                "short_description": item.get("short_description", ""),
                "long_description": item.get("long_description", ""),
                "gold_alignment_score": item.get("gold_alignment_score", 0.0),
                "normalized_type": item.get("normalized_type", ""),
            })

        return clean_items

    # ==================================================
    # ONTOLOGY CONTEXT
    # ==================================================

    def build_ontology_context(self, max_classes=80):
        """
        Intenta construir un contexto textual de clases ontológicas
        a partir de ontology_index sin asumir demasiado de su implementación.
        """
        class_lines = []

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

        elif hasattr(self.ontology_index, "get_all_classes"):
            try:
                all_classes = self.ontology_index.get_all_classes()
                for i, item in enumerate(all_classes):
                    if i >= max_classes:
                        break
                    class_lines.append(f"- {item}")
            except Exception:
                pass

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

Tu tarea es extraer ÚNICAMENTE instancias del website proporcionado.
MUY IMPORTANTE: SOLO ACEPTAR URLS DEL DOMINIO INICIAL PROPORCIONADO DONDE SE CUMPLA QUE HOSTNAME == DOMINIO_INICIAL

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
- actividades genéricas: eventos deportivos, actividades en familia o planes que no estén inequívocamente relacionados con el hecho turístico
- conceptos abstractos: gastronomía, patrimonio, tradición, folklore
- fragmentos de direcciones: A-4 Km, 41020 Sevilla, Av. de Kansas City
- números, códigos, teléfonos, horarios
- elementos de navegación web: ver listado, haz clic aquí, ir a página
- frases cortadas o concatenaciones artificiales: Museos De, Salir La, Cultura Artesanía Fiestas
- servicios genéricos sin nombre propio: taxi, autobús, metro, líneas de autobús
- términos demasiado genéricos que no designen una instancia concreta

REGLAS:
- Extrae solo fragmentos de texto relacionables con el turismo.
- No inventes instancias que no estén previamente presentes en el texto del website proporcionado.
- No unas palabras que no formen una instancia real del texto del dominio inicial.
- Prioriza instancias inequívocamente relacionadas con el turismo, con nombre propio o identidad concreta.
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
Eres un validador de instancias asociadas al turismo.

Tu tarea es extraer de una lista de instancias solo las que sean clasificables en alguna de las entidades turísticas proporcionadas, concretas e identificables.

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
- negocios identificables que pueden estar involucrados en la actividad turística
- instituciones asociadas al negocio turístico
- eventos de interés turístico concretos
- puntos de interés turístico con nombre reconocible

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

    def build_classification_prompt(self, entities, text, url=None):
        entities_json = json.dumps(entities, ensure_ascii=False)
        ontology_context = self.build_ontology_context()
        gold_context = self.build_gold_example_prompt_context(url) if url else ""

        return f"""
Eres un sistema experto en clasificación ontológica de instancias turísticas.

Se te proporciona:
1. Un texto de contexto.
2. Una lista de instancias candidatas, susceptibles de ser clasificadas según una ontología de turismo.
3. Una lista de entidades ontológicas dentro de las cuales se clasificarán las instancias candidatas.

DEFINICIÓN:
Una entidad ontológica de turismo es un elemento identificable relevante para el turista y enmarcado en el hecho turístico.

TU TAREA:
Clasificar cada instancia candidata en la entidad ontológica más adecuada, usando el contexto y la lista de entidades disponibles.

REGLAS IMPORTANTES:
- NO inventes nuevas entidades.
- NO cambies el nombre de las entidades.
- NO clasifiques categorías, conceptos o fragmentos.
- Si una entidad no es realmente válida, descártala.
- Si hay duda razonable entre varias, usa la entidad más general que encaje.
- No dejes sin clasificar ninguna entidad válida.
- Prioriza la entidad principal de la página frente a elementos laterales, relacionados o accesorios.
- Penaliza implícitamente elementos de bloques tipo “también te puede interesar”, navegación, servicios auxiliares o referencias secundarias.

ONTOLOGÍA TURÍSTICA:
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

EJEMPLOS ORIENTATIVOS:

Ejemplo 1
Input:
Visita al Real Alcázar de Sevilla, uno de los monumentos más importantes de la ciudad.

Output:
Name: Real Alcázar
Type: TouristAttraction
Reason: Es un monumento histórico relevante y visitable, claramente una atracción turística.

Ejemplo 2
Input:
La Semana Santa de Sevilla es una de las celebraciones religiosas más importantes de España.

Output:
Name: Semana Santa
Type: Event
Reason: Se trata de una celebración periódica con carácter cultural y religioso.

Ejemplo 3
Input:
Ruta de los Azulejos por el casco histórico de Sevilla.

Output:
Name: Ruta de los Azulejos
Type: Route
Reason: Es un itinerario turístico diseñado para recorrer distintos puntos de interés.

Ejemplo 4
Input:
El Ayuntamiento de Sevilla ofrece información turística y servicios al ciudadano.

Output:
Name: Ayuntamiento de Sevilla
Type: Organization
Reason: Es una entidad institucional que presta servicios públicos.

Ejemplo 5
Input:
Cena en el restaurante Abades Triana con vistas al río Guadalquivir.

Output:
Name: Abades Triana
Type: LocalBusiness
Reason: Es un establecimiento comercial de restauración.

Ejemplo 6
Input: 
Segunda plaza de toros histórica en Sevilla, un importante recurso cultural


Output:
Name: plaza de toros histórica
Type: bullring
Reason: La plaza de toros histórica de Sevilla es un importante monumento que refleja la tradición taurina de la ciudad.
Este lugar no solo es un espacio para corridas de toros, sino que también es un atractivo turístico que ofrece visitas guiadas y eventos culturales, destacando su arquitectura y su historia en el contexto de la cultura española


Ejemplo 7
Input:
Visita al Museo Nacional de Escultura en Valladolid.

Output:
Name: Museo Nacional de Escultura
Type: TouristAttraction
Reason: Es un museo abierto al público con interés cultural.

Ejemplo 8
Input:
La Plaza Mayor de Valladolid es el centro neurálgico de la ciudad.

Output:
Name: Plaza Mayor de Valladolid
Type: TouristAttraction
Reason: Es un lugar emblemático visitable y de interés turístico.

Ejemplo 9
Input:
La Semana Internacional de Cine de Valladolid (Seminci) es un evento cultural destacado.

Output:
Name: Seminci
Type: Event
Reason: Es un evento cultural periódico centrado en el cine.

Ejemplo 10
Input:
Ruta del vino de Rueda desde Valladolid.

Output:
Name: Ruta del vino de Rueda
Type: Route
Reason: Es un recorrido turístico temático relacionado con el vino.

Ejemplo 11
Input:
El Ayuntamiento de Valladolid gestiona los servicios municipales.

Output:
Name: Ayuntamiento de Valladolid
Type: Organization
Reason: Es una institución pública que administra servicios locales.

Ejemplo 12
Input:
Estadio de fútbol en Valladolid, sede de eventos deportivos.

Output:
Name: Estadio José Zorrilla
Type: Stadium
Reason: El Estadio José Zorrilla es un emblemático estadio de fútbol ubicado en Valladolid, España.
Es la casa del Real Valladolid y ha sido escenario de numerosos eventos deportivos y culturales.
Su ubicación en la Avenida Mundial 82 lo convierte en un punto de interés para los aficionados al deporte y los turistas que visitan la ciudad durante eventos importantes como la Semana Santa Blanquivioleta



{gold_context}

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

        if self.client is None:
            return default

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )

            content = response.choices[0].message.content.strip()
            return self.safe_json_parse(content)

        except Exception as e:
            print("LLM extract error:", e, file=sys.stderr)
            return default

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

    def analyze_entities(self, entities, text, url=None):
        if not entities:
            return []

        if url and normalize_url(url) in self.gold_examples:
            print(
                f"[LLM_SUPERVISOR][PROMPT_GOLD] usando ejemplo supervisado para {normalize_url(url)}",
                file=sys.stderr,
            )

        prompt = self.build_classification_prompt(entities, text, url=url)
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
                        "normalized_type": normalize_type(entity_class),
                        "score": score,
                        "short_description": short_description[:160],
                        "long_description": long_description[:400],
                    })

                if url:
                    clean_items = self.rerank_classified_entities(url, clean_items)

                return clean_items

        return []

    # ==================================================
    # FULL PIPELINE
    # ==================================================

    def extract_and_validate_entities(self, text):
        extracted = self.extract_entities(text)
        validated = self.validate_entities(extracted, text)
        return validated