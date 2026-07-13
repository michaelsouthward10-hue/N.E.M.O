class KnowledgeGraph:

    def __init__(self):

        self.graph = {}

    def add_note(self, name):

        if name not in self.graph:
            self.graph[name] = {
                "name": name,
                "connections": set()
            }

    def add_edge(self, source, target):

        self.add_note(source)
        self.add_note(target)

        if target not in self.graph[source]["connections"]:
            self.graph[source]["connections"].add(target)

    def connected_to(self,node):

        return self.graph.get(node, [])