from rdflib import Graph, RDFS
from sentence_transformers import SentenceTransformer


CLASS_EXPANSION = {
    "BullRing": ["bull ring", "plaza de toros", "arena"],
    "Museum": ["museum", "museo"],
    "Beach": ["beach", "playa"],
    "Square": ["square", "plaza"],
    "Bridge": ["bridge", "puente"],
    "Park": ["park", "parque"],
    "Hotel": ["hotel", "alojamiento"],
    "Restaurant": ["restaurant", "restaurante"],
    "OutdoorEvent": ["evento", "festival", "carnaval", "fiesta"]
}

CLASS_CONTEXT = {
    "Museum": "museo arte exposición cultural",
    "Beach": "playa arena mar costa turismo",
    "Square": "plaza centro urbano espacio público",
    "Park": "parque jardín naturaleza zona verde",
    "Bridge": "puente río estructura paso",
    "Hotel": "hotel alojamiento turismo habitación",
    "Restaurant": "restaurante comida gastronomía",
    "OutdoorEvent": "evento festival carnaval celebración fiesta",
    "Church": "church iglesia templo religioso patrimonio",
    "BullRing": "plaza de toros arena corrida taurina",
    

}




class OntologyIndex:




    def __init__(self, rdf_path):

        # cargar ontología
        self.graph = Graph()
        self.graph.parse(rdf_path)

        self.labels = []
        self.uris = []

        # diccionario URI → label
        self.uri_to_label = {}

        # cache jerárquica
        self.hierarchy_cache = {}

        # cargar clases
        for s in self.graph.subjects():

            for label in self.graph.objects(s, RDFS.label):

                uri = str(s)
                label_str = str(label)

                
                
            
                context = label_str

                if label_str in CLASS_CONTEXT:
                    context += " " + CLASS_CONTEXT[label_str]

                self.labels.append(context)
                self.uris.append(uri) 




                # añadir labels expandidos
                if label_str in CLASS_EXPANSION:

                    for alt in CLASS_EXPANSION[label_str]:

                        self.labels.append(alt)
                        self.uris.append(uri)




                self.uri_to_label[uri] = label_str

        # modelo de embeddings
        self.model = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2"
        )

        # crear embeddings de clases
        self.embeddings = self.model.encode(self.labels)

        # precalcular jerarquía completa
        self._build_hierarchy_cache()


    def _build_hierarchy_cache(self):

        """
        Precalcula jerarquía de todas las clases
        """

        for uri in self.uris:

            hierarchy = []
            visited = set()
            stack = [uri]

            while stack:

                current = stack.pop()

                if current in visited:
                    continue

                visited.add(current)

                parents = list(
                    self.graph.objects(current, RDFS.subClassOf)
                )

                for p in parents:

                    parent_uri = str(p)

                    hierarchy.append(parent_uri)

                    stack.append(parent_uri)

            self.hierarchy_cache[uri] = hierarchy


    def get_hierarchy(self, uri):

        """
        Devuelve jerarquía precalculada
        """

        return self.hierarchy_cache.get(uri, [])


    def get_label(self, uri):

        """
        Obtener etiqueta de una URI
        """

        return self.uri_to_label.get(uri)