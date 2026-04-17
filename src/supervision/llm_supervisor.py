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
    GENERIC_REJECT_CLASSES = {
        "thing",
        "location",
        "place",
        "person",
        "entity",
        "resource",
    }

    BAD_ENTITY_PATTERNS = [
        r"\bfacebook\b",
        r"\binstagram\b",
        r"\bsuscr[ií]bete\b",
        r"\bmapas\b",
        r"\bconsignas\b",
        r"\bplanes\b",
        r"\bqu[eé]\b",
        r"\bver\b",
        r"\bultimas?\b",
        r"\bagenda\b",
        r"\bmultitud\b",
        r"\bfamilia\b",
        r"\bgastronom[ií]a\b",
        r"\bcultura\b",
        r"\btradiciones\b",
        r"\bturismo responsable\b",
        r"\bdestino tur[ií]stico sostenible\b",
        r"\binter[eé]s tur[ií]stico internacional\b",
        r"\bdesarrollo sostenible\b",
        r"\bnaciones unidas\b",
    ]

    BAD_EXACT_ENTITIES = {
        "gora san fermín",
        "facebook instagram",
        "monumentos mercados últimas",
        "suscríbete nuestros",
        "pamplona viajar",
        "pamplona ver",
        "planes excursiones",
        "planes cultura",
        "planes qué",
        "agenda multitud",
        "historia verde",
        "historia en",
        "destino turístico sostenible",
        "interés turístico internacional",
        "turismo responsable",
        "desarrollo sostenible",
        "certificación biosphere",
        "biosphere pamplona",
    }

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

        self.allowed_classes = self._load_allowed_classes()

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
    # ONTOLOGY HELPERS
    # ==================================================

    def _load_allowed_classes(self):
        allowed = set()

        if hasattr(self.ontology_index, "classes"):
            classes_obj = getattr(self.ontology_index, "classes")
            if isinstance(classes_obj, dict):
                allowed.update(str(k).strip() for k in classes_obj.keys() if str(k).strip())
            elif isinstance(classes_obj, list):
                for item in classes_obj:
                    if isinstance(item, str):
                        allowed.add(item.strip())
                    elif isinstance(item, dict) and item.get("name"):
                        allowed.add(str(item["name"]).strip())

        elif hasattr(self.ontology_index, "get_all_classes"):
            try:
                for item in self.ontology_index.get_all_classes():
                    if isinstance(item, str):
                        allowed.add(item.strip())
                    elif isinstance(item, dict) and item.get("name"):
                        allowed.add(str(item["name"]).strip())
            except Exception:
                pass

        return {c for c in allowed if c}

    def build_ontology_context(self, max_classes=80):
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
    # GOLD PRIOR / GOLD PROMPT
    # ==================================================

    def normalize_llm_class(self, value: str) -> str:
        if not value:
            return ""
        return normalize_type(value)

    def build_gold_example_prompt_context(self, url: str) -> str:
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
    # ENTITY QUALITY FILTERS
    # ==================================================

    def normalize_entity_text(self, value: str) -> str:
        value = str(value or "").strip()
        value = re.sub(r"\s+", " ", value)
        return value

    def is_bad_entity_name(self, entity: str) -> bool:
        entity = self.normalize_entity_text(entity)
        if not entity:
            return True

        entity_l = entity.lower()

        if entity_l in self.BAD_EXACT_ENTITIES:
            return True

        if len(entity) < 3:
            return True

        if len(entity.split()) > 7:
            return True

        if re.fullmatch(r"[\W\d_]+", entity):
            return True

        if re.search(r"\b(siglos?|origen|historia|descubre|pamplona bizi-bizirik)\b", entity_l):
            return True

        if re.search(r"\b(aquí|allí|muy viva|últimas|ver listado|haz clic)\b", entity_l):
            return True

        for pat in self.BAD_ENTITY_PATTERNS:
            if re.search(pat, entity_l, flags=re.IGNORECASE):
                return True

        tokens = entity_l.split()
        if len(tokens) >= 2 and len(set(tokens)) == 1:
            return True

        return False

    def dedupe_entities(self, entities: list[str]) -> list[str]:
        seen = set()
        clean = []

        for e in entities:
            e = self.normalize_entity_text(e)
            key = e.lower()
            if not e or key in seen:
                continue
            seen.add(key)
            clean.append(e)

        return clean

    def is_valid_class(self, class_name: str) -> bool:
        if not class_name:
            return False

        raw = str(class_name).strip()
        normalized = self.normalize_llm_class(raw).strip().lower()

        if not normalized:
            return False

        if normalized in self.GENERIC_REJECT_CLASSES:
            return False

        if self.allowed_classes:
            raw_ok = raw in self.allowed_classes
            norm_ok = any(self.normalize_llm_class(c).lower() == normalized for c in self.allowed_classes)
            if not raw_ok and not norm_ok:
                return False

        return True

    def calibrate_score(self, entity: str, class_name: str, llm_score: float) -> float:
        score = max(0.0, min(1.0, float(llm_score)))

        if self.is_bad_entity_name(entity):
            score *= 0.15

        if not self.is_valid_class(class_name):
            score *= 0.10

        if len(entity.split()) == 1:
            score *= 0.80

        entity_l = entity.lower()
        if re.search(r"\b(san|santa|santo)\b", entity_l) and len(entity.split()) == 2:
            score *= 0.75

        if score > 0.95:
            score = 0.92

        return round(score, 4)

    def filter_classified_items(self, items: list[dict]) -> list[dict]:
        filtered = []
        seen = set()

        for item in items:
            entity = self.normalize_entity_text(item.get("entity", ""))
            entity_class = str(item.get("class", "")).strip()
            score = float(item.get("score", 0.0))

            if not entity or not entity_class:
                continue

            if self.is_bad_entity_name(entity):
                continue

            if not self.is_valid_class(entity_class):
                continue

            if score < 0.45:
                continue

            key = (entity.lower(), self.normalize_llm_class(entity_class).lower())
            if key in seen:
                continue
            seen.add(key)

            filtered.append(item)

        return filtered

    # ==================================================
    # PROMPTS
    # ==================================================

    def build_extraction_prompt(self, text):
        return f"""
Eres un agente de turismo experto en extracción de instancias turisticas de un website que se te proporciona

Tu tarea es UNICAMENTE EXTRAER instancias turísticas del website proporcionado.

DEFINICIÓN DE INSTANCIA DE TURISMO:
Una instancia es un OBJETO MATERIAL, CONCRETO, NOMBRADO y RELEVANTE TURISTICAMENTE.

MUY IMPORTANTE:
- Solo extrae entidades con nombre identificable.
- No extraigas fragmentos cortados.
- No extraigas concatenaciones artificiales.
- No extraigas lemas, slogans, menús, botones, breadcrumbs, secciones, hashtags o texto de navegación.
- No extraigas personas salvo que aparezcan como recurso turístico explícito y visitable.
- No extraigas certificaciones, declaraciones, premios, etiquetas, campañas o conceptos abstractos.

EJEMPLOS VÁLIDOS:
- ciudades, barrios, lugares y destinos
- monumentos, museos, parques, plazas, playas
- aeropuertos, estaciones, terminales, muelles
- hoteles, restaurantes, empresas turísticas
- eventos concretos con identidad propia
- instituciones u organizaciones estrechamente relacionadas con el turismo

NO EXTRAIGAS COMO ENTIDADES:
- categorías o secciones del site
- actividades genéricas
- conceptos abstractos
- fragmentos de dirección
- números, códigos, teléfonos, horarios
- elementos de navegación web
- frases cortadas o concatenaciones artificiales
- servicios genéricos sin nombre propio
- términos demasiado genéricos
- personas históricas, medios, instituciones globales o marcas si no son el recurso turístico principal del texto

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
Eres un VALIDADOR de instancias asociadas al turismo.

Tu tarea es conservar SOLO entidades turísticas concretas, visitables, identificables o claramente relevantes como recurso turístico.

ELIMINA SIEMPRE:
- categorías
- conceptos abstractos
- actividades genéricas
- fragmentos de dirección
- números, códigos, teléfonos
- texto cortado
- concatenaciones artificiales
- duplicados
- expresiones demasiado genéricas sin identidad propia
- slogans, claims, menús, navegación, footer, redes sociales
- certificaciones, reconocimientos, agendas, etiquetas promocionales
- personas, periódicos, instituciones globales o nombres históricos si no son el recurso turístico principal

MANTÉN:
- topónimos concretos
- monumentos
- museos
- plazas, parques y barrios con nombre propio
- infraestructuras de transporte
- negocios identificables
- instituciones turísticas locales
- eventos concretos
- puntos de interés con nombre reconocible

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

        allowed_classes_line = ", ".join(sorted(self.allowed_classes)) if self.allowed_classes else "Usa solo clases de la ontología dada"

        return f"""
Eres un sistema experto en CLASIFICACION ONTOLOGICA de instancias turísticas.

Se te proporciona:
1. Un texto de contexto.
2. Instancias candidatas.
3. Una lista de clases ontológicas permitidas.

TU TAREA:
Clasificar SOLO las instancias verdaderamente válidas y devolver SOLO aquellas cuya clase sea específica y pertenezca a la ontología.

REGLAS CRÍTICAS:
- ELIGE EXCLUSIVAMENTE UNA CLASE REAL DE LA ONTOLOGÍA
- NO DEJES NINGUNA INSTANCIA SIN CLASIFICAR ONTOLOGICAMENTE
- SI LA ÚNICA CLASE POSIBLE ES Thing, Place, Location, Person u otra genérica: DESCARTA LA ENTIDAD
- SI LA ENTIDAD ES ABSTRACTA, PROMOCIONAL, CORTADA O DE NAVEGACIÓN: DESCÁRTALA
- NO CAMBIES EL NOMBRE DE LA ENTIDAD
- NO INVENTES CLASES NUEVAS
- NO FUERCES CLASIFICACIONES
- NO DEVUELVAS ENTIDADES DUDOSAS

CLASES PERMITIDAS:
{allowed_classes_line}

ONTOLOGÍA TURÍSTICA:
{ontology_context}

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
- NO uses 1.0 salvo evidencia extremadamente clara
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
                entities = [str(e).strip() for e in entities if str(e).strip()]
                entities = self.dedupe_entities(entities)
                entities = [e for e in entities if not self.is_bad_entity_name(e)]
                return entities

        return []

    def validate_entities(self, entities, text):
        if not entities:
            return []

        prompt = self.build_validation_prompt(entities, text)
        data = self.call_llm_json(prompt, default={"entities": []})

        if isinstance(data, dict):
            clean_entities = data.get("entities", [])
            if isinstance(clean_entities, list):
                clean_entities = [str(e).strip() for e in clean_entities if str(e).strip()]
                clean_entities = self.dedupe_entities(clean_entities)
                clean_entities = [e for e in clean_entities if not self.is_bad_entity_name(e)]
                return clean_entities

        return []

    def analyze_entities(self, entities, text, url=None):
        if not entities:
            return []

        entities = self.dedupe_entities(entities)
        entities = [e for e in entities if not self.is_bad_entity_name(e)]
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

                    entity = self.normalize_entity_text(item.get("entity", ""))
                    entity_class = str(item.get("class", "")).strip()

                    if not entity or not entity_class:
                        continue

                    try:
                        raw_score = float(item.get("score", 0.5))
                    except Exception:
                        raw_score = 0.5

                    raw_score = max(0.0, min(1.0, raw_score))
                    score = self.calibrate_score(entity, entity_class, raw_score)

                    short_description = str(item.get("short_description", "")).strip()
                    long_description = str(item.get("long_description", "")).strip()

                    clean_items.append({
                        "entity": entity,
                        "class": entity_class,
                        "normalized_type": normalize_type(entity_class),
                        "score": score,
                        "short_description": short_description[:160],
                        "long_description": long_description[:400],
                    })

                clean_items = self.filter_classified_items(clean_items)

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

    # ==================================================
    # FINAL HARD FILTER FOR POST-PROCESSING / ENRICHMENT
    # ==================================================

    def final_entity_guard(self, entities: list[dict]) -> list[dict]:
        CLEAN_TYPES = {
            "TownHall", "Square", "Park", "Museum",
            "Restaurant", "Event", "TouristAttraction",
            "Accommodation", "Monument", "Route",
            "BullRing", "Basilica", "Cathedral",
            "Castle", "ArcheologicalSite",
            "HistoricalOrCulturalResource",
            "EventOrganisationCompany",
            "LocalBusiness", "Organization",
            "TransportInfrastructure",
        }

        GENERIC_TYPES = {
            "thing", "location", "place", "entity"
        }

        BAD_NAME_PATTERNS = [
            r"\bplanes\b",
            r"\bagenda\b",
            r"\bmapas\b",
            r"\bsuscr",
            r"\bfacebook\b",
            r"\binstagram\b",
            r"\bqué\b",
            r"\bver\b",
            r"\búltimas\b",
            r"\bgastronom[ií]a\b",
            r"\bcultura\b",
            r"\bfamilia\b",
            r"\btradiciones\b",
        ]

        def is_bad_name(name: str) -> bool:
            name_l = str(name or "").lower().strip()
            if not name_l:
                return True

            if len(name_l.split()) > 6:
                return True

            for p in BAD_NAME_PATTERNS:
                if re.search(p, name_l):
                    return True

            tokens = name_l.split()
            if len(tokens) >= 2 and len(set(tokens)) == 1:
                return True

            return False

        def get_clean_types(types: list[str]) -> list[str]:
            if not types:
                return []

            clean = []
            seen = set()

            for t in types:
                if not t:
                    continue

                t = str(t).strip()
                t_l = t.lower()

                if t_l in GENERIC_TYPES:
                    continue

                if t in CLEAN_TYPES and t not in seen:
                    seen.add(t)
                    clean.append(t)

            return clean

        filtered = []

        for e in entities:
            if not isinstance(e, dict):
                continue

            name = self.normalize_entity_text(e.get("name", ""))
            types = e.get("types", [])

            if not name:
                continue

            if is_bad_name(name):
                continue

            clean_types = get_clean_types(types)
            if not clean_types:
                continue

            e["name"] = name
            e["types"] = clean_types

            try:
                e["score"] = min(float(e.get("score", 0.5)), 0.9)
            except Exception:
                e["score"] = 0.5

            filtered.append(e)

        return filtered

    def is_geo_valid(self, entity: str, lat, lng) -> bool:
        if lat is None or lng is None:
            return True

        return (
            41.5 <= lat <= 43.5 and
            -3.5 <= lng <= -0.5
        )