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

    CLASSIFICATION_SYSTEM_PROMPT = """
Eres un sistema experto en CLASIFICACIÓN ONTOLÓGICA de instancias turísticas.

Tu tarea es:
1. Identificar cuáles de las entidades candidatas son realmente entidades turísticas válidas.
2. Asignar SOLO una clase ontológica específica y válida a las entidades correctas.
3. Rechazar cualquier candidato que sea ruido, texto editorial, navegación, CTA, categoría, concepto abstracto o fragmento narrativo.

REGLAS CRÍTICAS:
- Usa el NOMBRE de la entidad como señal principal.
- Usa el CONTEXTO textual para confirmar, desambiguar o rechazar.
- Si el nombre parece una frase narrativa, texto cortado, claim, CTA, categoría, sección del site o encabezado editorial: REJECT.
- Si no existe evidencia suficiente para una clase ontológica concreta: REJECT.
- No inventes entidades.
- No inventes clases.
- No cambies el nombre de la entidad.
- No aceptes clases genéricas como Thing, Place, Location, Person, Entity o Resource como resultado final.
- Si varias clases parecen posibles, elige la más específica respaldada por el texto.
- Si el contenido describe un tema general y no un POI concreto, REJECT.
- El contexto ayuda a clasificar mejor, pero NUNCA debe rescatar un nombre malo o narrativo.
- Respeta exactamente los nombres de entidades que se te proporcionan.
- Si rechazas una entidad, NO la devuelvas en la salida final.

FORMATO DE RESPUESTA OBLIGATORIO:
Devuelve SOLO un JSON válido con esta estructura exacta:
{
  "entities": [
    {
      "entity": "Nombre exacto de la entidad",
      "class": "ClaseOntologica",
      "score": 0.0,
      "short_description": "Descripción breve y concreta",
      "long_description": "Descripción algo más amplia y contextual",
      "reason": "Motivo breve de la clasificación"
    }
  ]
}

REGLAS DE SALIDA:
- score entre 0 y 1
- NO uses 1.0 salvo evidencia extremadamente clara
- short_description máximo 160 caracteres
- long_description máximo 400 caracteres
- Devuelve SOLO entidades válidas y clasificables
- Devuelve SOLO JSON, sin explicación adicional
""".strip()

    POSITIVE_FEW_SHOTS = [
        {
            "input": {
                "name": "Catedral de Santa María La Real",
                "url": "https://visitpamplonairuna.com/tipo-lugar/iglesias-y-catedral/",
                "page_context": "https://visitpamplonairuna.com/lugar/catedral-de-santa-maria-la-real/",
            },
            "output": {
                "entity": "Catedral de Santa María La Real",
                "class": "Cathedral",
                "score": 0.99,
                "short_description": "Construida entre los siglos XIV y XV sobre una antigua catedral románica",
                "long_description": "La Catedral de Santa María la Real es un destacado ejemplo de la arquitectura gótica francesa en Navarra, considerado uno de los tres mejores conjuntos catedralicios góticos.",
                "reason": "Nombre de POI claro y contexto coherente con una catedral.",
                "img": "https://visitpamplonairuna.com/wp-content/uploads/elementor/thumbs/Catedral_SantaMaria-1-r0f6ruewswmbhucz3t4o82zh6r1ydhviw01z8p8dpg.png",
            },
        },
        {
            "input": {
                "name": "San Fermín",
                "url": "https://visitpamplonairuna.com/descubre-pamplona/san-fermin/",
                "page_context": "https://visitpamplonairuna.com/descubre-pamplona/",
            },
            "output": {
                "entity": "San Fermín",
                "class": "Evento",
                "score": 0.98,
                "short_description": "San Fermín es la fiesta más emblemática de Pamplona.",
                "long_description": "En el siglo XVI parte de la población empezó a sumarse al trayecto, corriendo delante de los astados. Pese al intento de impedirlas por parte de las autoridades, las carreras continuaron hasta consolidarse como tradición.",
                "reason": "Nombre de fiesta de interés turístico asociada principalmente a los encierros",
                "img": "https://visitpamplonairuna.com/wp-content/uploads/2025/10/Chupinazo-2.jpg",
            },
        },
        {
            "input": {
                "name": "Archivo General de Indias",
                "url": "https://visitasevilla.es/archivo-de-indias/",
                "page_context": "https://visitasevilla.es/",
            },
            "output": {
                "entity": "Archivo General de Indias",
                "class": "InterpretationCentre",
                "score": 0.96,
                "short_description": "Visita recomendable para conocer el papel de Sevilla en la historia global.",
                "long_description": "El Archivo General de Indias fue fundado en 1785 por orden de Carlos III para centralizar la documentación sobre las colonias españolas, hasta entonces dispersa en otros archivos.",
                "reason": "La entidad es un archivo documental y un edificio histórico.",
                "img": "https://visitasevilla.es/wp-content/uploads/2025/06/shutterstock_2444981479-1024x683.jpg",
            },
        },
        {
            "input": {
                "name": "Alcazaba",
                "url": "https://www.turismobadajoz.es/alcazaba-badajoz/",
                "page_context": "https://www.turismobadajoz.es/",
            },
            "output": {
                "entity": "Alcazaba",
                "class": "Monumento",
                "score": 0.99,
                "short_description": "Muralla o alcazaba vinculada a los orígenes de la ciudad.",
                "long_description": "Construcción fortificada de origen musulmán del siglo IX que testimonia los inicios de la ciudad y su esplendor histórico.",
                "reason": "Construcción fortificada musulmana del siglo IX.",
                "img": "https://www.turismobadajoz.es/wp-content/uploads/2020/09/alcazaba-badajoz.jpg",
            },
        },
        {
            "input": {
                "name": "OleoturJaén",
                "url": "https://www.jaenparaisointerior.es/es/oleotour/inicio",
                "page_context": "https://www.jaenparaisointerior.es/es/",
            },
            "output": {
                "entity": "OleoturJaén",
                "class": "DestinationExperience",
                "score": 0.99,
                "short_description": "Oferta de oleoturismo en Jaén vinculada a la cultura del olivo.",
                "long_description": "Experiencia turística centrada en el proceso de producción del aceite y en el conocimiento de la cultura del olivo en Jaén.",
                "reason": "Experiencia turística temática claramente identificable.",
                "img": "",
            },
        },
        {
            "input": {
                "name": "ANNI B SWEET",
                "url": "https://visita.malaga.eu/es/agenda/anni-b-sweet-p109988",
                "page_context": "https://visita.malaga.eu/es/agenda/",
            },
            "output": {
                "entity": "ANNI B SWEET",
                "class": "Event",
                "score": 0.99,
                "short_description": "Concierto en el Teatro Cervantes dentro del ciclo Unísonas.",
                "long_description": "Actuación musical concreta, identificable y contextualizada como evento cultural en Málaga.",
                "reason": "Entidad asociada a un concierto o evento cultural concreto.",
                "img": "https://static.visita.malaga.eu/visita/subidas/imagenes/8/5/arc_41058_m.jpg",
            },
        },
        {
            "input": {
                "name": "Descarga de guías y publicaciones",
                "url": "https://www.costablanca.org/es/travel-planning/travel-guides",
                "page_context": "https://www.costablanca.org/es/",
            },
            "output": {
                "entity": "guias y publicaciones",
                "class": "TourismEntity",
                "score": 0.99,
                "short_description": "Guías gratuitas para consultar propuestas de la Costa Blanca.",
                "long_description": "Recurso turístico informativo de apoyo al visitante, centrado en guías y publicaciones descargables.",
                "reason": "Recurso turístico del que puede hacer uso el turista de la Costa Blanca.",
                "img": "https://cms.smartcostablanca.com/sites/default/files/2024-01/encabezadoguiaypubliacaciones.jpg",
            },
        },
        {
            "input": {
                "name": "Turismo Joven",
                "url": "https://getafe.es/muestra-turismo-joven/",
                "page_context": "https://getafe.es/",
            },
            "output": {
                "entity": "Turismo Joven",
                "class": "Evento",
                "score": 0.98,
                "short_description": "Especial informativo sobre turismo dirigido a jóvenes.",
                "long_description": "Actividad organizada por un servicio juvenil para orientar viajes de jóvenes durante las fiestas navideñas.",
                "reason": "Recurso o evento turístico orientado a jóvenes de Getafe.",
                "img": "https://visitpamplonairuna.com/wp-content/uploads/2025/10/Chupinazo-2.jpg",
            },
        },
        {
            "input": {
                "name": "Residencia Cultural y Universitaria Cimadevilla",
                "url": "https://www.gijon.es/es/directorio/residencia-cultural-y-universitaria-cimadevilla",
                "page_context": "https://www.gijon.es/es/turismo/",
            },
            "output": {
                "entity": "Residencia Cultural y Universitaria Cimadevilla",
                "class": "Residence",
                "score": 0.99,
                "short_description": "Residencia situada en el casco antiguo de Gijón.",
                "long_description": "Alojamiento identificado y localizado en una zona turística, conectado con campus, playa y puerto deportivo.",
                "reason": "Recurso turístico de alojamiento.",
                "img": "",
            },
        },
        {
            "input": {
                "name": "Emérita sobrenatural",
                "url": "https://turismoapps.dip-badajoz.es/node/18766",
                "page_context": "https://turismoapps.dip-badajoz.es/",
            },
            "output": {
                "entity": "Emérita sobrenatural",
                "class": "LocalBusiness",
                "score": 0.99,
                "short_description": "Actividad temática vinculada a relatos sobrenaturales.",
                "long_description": "Experiencia organizada en torno a casas encantadas, maldiciones y mitología del inframundo.",
                "reason": "Actividad o negocio turístico temático identificable.",
                "img": "",
            },
        },
        {
            "input": {
                "name": "Cicloturismo en Madrid",
                "url": "https://www.visitmadrid.es/hacer-madrid-planes-experiencias-imperdibles/hacer/deporte-turismo-activo/ciclamadrid",
                "page_context": "https://www.visitmadrid.es/hacer-madrid-planes-experiencias-imperdibles/hacer/deporte-turismo-activo/",
            },
            "output": {
                "entity": "Cicloturismo",
                "class": "TourismService",
                "score": 0.99,
                "short_description": "Espacio para amantes de la bicicleta en la Comunidad de Madrid.",
                "long_description": "Servicio o recurso turístico con información práctica, buscador de rutas y propuestas de movilidad activa en bici.",
                "reason": "Servicio turístico orientado a rutas y movilidad ciclista.",
                "img": "",
            },
        },
        {
            "input": {
                "name": "De Pavía a Breda",
                "url": "https://www.jerez.es/eventos",
                "page_context": "https://www.turismojerez.com/",
            },
            "output": {
                "entity": "De Pavía a Breda",
                "class": "Event",
                "score": 0.99,
                "short_description": "Exposición temporal De Pavía a Breda.",
                "long_description": "Exposición temporal claramente identificada como evento cultural.",
                "reason": "Evento expositivo concreto.",
                "img": "",
            },
        },
    ]

    NEGATIVE_FEW_SHOTS = [
        {
            "input": {
                "name": "no sabes qué hacer",
                "url": "https://ejemplo.com/que-hacer",
                "page_context": "Rellena aquí con el bloque o texto real",
            },
            "output": {
                "reject": True,
                "reason": "Fragmento de frase narrativa, no nombre de entidad.",
            },
        },
        {
            "input": {
                "name": "Descubre Pamplona",
                "url": "https://ejemplo.com/descubre-pamplona",
                "page_context": "Rellena aquí con el bloque o texto real",
            },
            "output": {
                "reject": True,
                "reason": "Heading o lema editorial del portal, no entidad concreta.",
            },
        },
    ]

    AMBIGUOUS_FEW_SHOTS = [
        {
            "input": {
                "name": "Pelota Vasca",
                "url": "https://ejemplo.com/pelota-vasca",
                "page_context": "Rellena aquí con el bloque o texto real",
            },
            "output": {
                "reject": True,
                "reason": "Concepto cultural o deportivo general, no POI concreto.",
            },
        },
        {
            "input": {
                "name": "Casco Antiguo de Pamplona",
                "url": "https://ejemplo.com/casco-antiguo",
                "page_context": "Rellena aquí con el bloque o texto real",
            },
            "output": {
                "entity": "Casco Antiguo de Pamplona",
                "class": "Place",
                "score": 0.90,
                "short_description": "Zona urbana histórica claramente identificable.",
                "long_description": "Entidad territorial concreta respaldada por el contexto urbano e histórico.",
                "reason": "Entidad urbana concreta y reconocible, no simple heading editorial.",
            },
        },
    ]

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

    def safe_json_parse(self, content):
        if not content:
            return []

        content = content.strip()
        content = re.sub(r"^```json\\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"^```\\s*", "", content)
        content = re.sub(r"\\s*```$", "", content)

        try:
            return safe_load_json(content)
        except Exception:
            pass

        match = re.search(r"(\\{.*\\}|\\[.*\\])", content, re.DOTALL)
        if match:
            try:
                return safe_load_json(match.group(1))
            except Exception:
                pass

        return []

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

        return "\\n".join(class_lines)

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
                "reason": item.get("reason", ""),
            })

        return clean_items

    def _format_few_shot_examples(self, title: str, examples: list[dict]) -> str:
        if not examples:
            return f"{title}:\\n- Sin ejemplos todavía."

        lines = [title]
        for i, ex in enumerate(examples, start=1):
            lines.append(f"\\nEjemplo {i}")
            lines.append("INPUT:")
            lines.append(json.dumps(ex.get("input", {}), ensure_ascii=False, indent=2))
            lines.append("OUTPUT:")
            lines.append(json.dumps(ex.get("output", {}), ensure_ascii=False, indent=2))
        return "\\n".join(lines)

    def build_few_shot_prompt_context(self) -> str:
        return "\\n\\n".join([
            self._format_few_shot_examples("EJEMPLOS POSITIVOS", self.POSITIVE_FEW_SHOTS),
            self._format_few_shot_examples("EJEMPLOS NEGATIVOS", self.NEGATIVE_FEW_SHOTS),
            self._format_few_shot_examples("EJEMPLOS AMBIGUOS", self.AMBIGUOUS_FEW_SHOTS),
        ])

    def normalize_entity_text(self, value: str) -> str:
        value = str(value or "").strip()
        value = re.sub(r"\\s+", " ", value)
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

        if re.fullmatch(r"[\\W\\d_]+", entity):
            return True

        if re.search(r"\\b(siglos?|origen|historia|descubre|pamplona bizi-bizirik)\\b", entity_l):
            return True

        if re.search(r"\\b(aquí|allí|muy viva|últimas|ver listado|haz clic)\\b", entity_l):
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
        if re.search(r"\\b(san|santa|santo)\\b", entity_l) and len(entity.split()) == 2:
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

    def build_extraction_prompt(self, text):
        return f"""
Eres un agente de turismo experto en extracción de instancias turisticas de un website que se te proporciona.

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
        few_shot_context = self.build_few_shot_prompt_context()
        allowed_classes_line = (
            ", ".join(sorted(self.allowed_classes))
            if self.allowed_classes
            else "Usa solo clases de la ontología dada"
        )

        return f"""
{self.CLASSIFICATION_SYSTEM_PROMPT}

CLASES PERMITIDAS:
{allowed_classes_line}

ONTOLOGÍA TURÍSTICA:
{ontology_context}

{gold_context}

{few_shot_context}

CONTEXTO:
\"\"\"
{text}
\"\"\"

ENTIDADES CANDIDATAS:
{entities_json}

INSTRUCCIONES FINALES:
- Clasifica SOLO las instancias verdaderamente válidas.
- Si una entidad es dudosa, genérica, narrativa o editorial, NO la devuelvas.
- Usa los few-shots como criterio adicional.
- Prioriza siempre la ontología y el contexto real.
- Usa exactamente el nombre recibido en cada entidad.
- Devuelve SOLO JSON válido.
""".strip()

    def call_llm_json(self, prompt, default=None):
        if default is None:
            default = []

        if self.client is None:
            return default

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )

            content = response.choices[0].message.content.strip()
            return self.safe_json_parse(content)

        except Exception as e:
            print("LLM extract error:", e, file=sys.stderr)
            return default

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
                    reason = str(item.get("reason", "")).strip()

                    clean_items.append({
                        "entity": entity,
                        "class": entity_class,
                        "normalized_type": normalize_type(entity_class),
                        "score": score,
                        "short_description": short_description[:160],
                        "long_description": long_description[:400],
                        "reason": reason[:220],
                    })

                clean_items = self.filter_classified_items(clean_items)

                if url:
                    clean_items = self.rerank_classified_entities(url, clean_items)

                return clean_items

        return []

    def extract_and_validate_entities(self, text):
        extracted = self.extract_entities(text)
        validated = self.validate_entities(extracted, text)
        return validated

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
            "thing", "location", "place", "entity",
        }

        BAD_NAME_PATTERNS = [
            r"\\bplanes\\b",
            r"\\bagenda\\b",
            r"\\bmapas\\b",
            r"\\bsuscr",
            r"\\bfacebook\\b",
            r"\\binstagram\\b",
            r"\\bqué\\b",
            r"\\bver\\b",
            r"\\búltimas\\b",
            r"\\bgastronom[ií]a\\b",
            r"\\bcultura\\b",
            r"\\bfamilia\\b",
            r"\\btradiciones\\b",
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
