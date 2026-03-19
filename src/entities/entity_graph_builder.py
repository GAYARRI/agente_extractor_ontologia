class EntityGraphBuilder:

    def __init__(self):
        self.graph = {}

    def add_relations(self, relations):

        for r in relations:

            subj = r.get("subject")
            obj = r.get("object")

            if not subj or not obj:
                continue

            key = (subj, obj)

            self.graph[key] = self.graph.get(key, 0) + 1

    def get_graph(self):
        return self.graph