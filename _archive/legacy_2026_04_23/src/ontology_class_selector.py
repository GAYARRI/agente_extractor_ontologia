from rdflib import Graph, Namespace, RDFS


class OntologyDrivenClassSelector:

    def __init__(self, ontology_path):

        self.graph = Graph()

        # cargar ontología
        self.graph.parse(ontology_path)

        self.ONTO = Namespace("http://tourismkg.com/ontology/")


    # ---------------------------------------------------
    # subclasses de una clase
    # ---------------------------------------------------

    def get_subclasses(self, class_name):

        subclasses = []

        class_uri = self.ONTO[class_name]

        for s in self.graph.subjects(RDFS.subClassOf, class_uri):

            subclasses.append(s.split("/")[-1])

        return subclasses


    # ---------------------------------------------------
    # subclasses de múltiples clases
    # ---------------------------------------------------

    def get_subclasses_multi(self, class_list):

        all_classes = []

        for c in class_list:

            all_classes.append(c)

            subclasses = self.get_subclasses(c)

            all_classes.extend(subclasses)

        return list(set(all_classes))