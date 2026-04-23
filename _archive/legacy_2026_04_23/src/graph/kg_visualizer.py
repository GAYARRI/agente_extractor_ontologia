from graphviz import Digraph


class KGVisualizer:

    def visualize(self, graph, output="kg_graph"):

        dot = Digraph()

        for s, p, o in graph:

            dot.node(str(s))
            dot.node(str(o))

            dot.edge(str(s), str(o), label=str(p))

        dot.render(output, format="png", view=True)