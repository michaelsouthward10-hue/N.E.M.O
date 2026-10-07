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
        if node not in self.graph:
            return set()

        return self.graph.get(node)["connections"]
    
    def find_path(self, start, goal):
        
        if start == goal:
            return [start]
        
        visited = set()

        queue = [[start]]

        while queue:

            path = queue.pop(0)
            node = path[-1]

            if node in visited:
                continue
            
            visited.add(node)

            for neighbour in self.connected_to(node):

                new_path = path + [neighbour]

                if neighbour == goal:
                    return new_path
                
                queue.append(new_path)

        return None

    def build(self, index):

        self.graph.clear()

        for note in index.values():

            source = note["title"]

            self.add_note(source)

            for link in note.get("links", []):

                self.add_edge(source, link)

    def connected_from(self, node):

        connected = []

        for source, targets in self.graph.items():

            if node in targets:
                connected.append(source)

        return connected