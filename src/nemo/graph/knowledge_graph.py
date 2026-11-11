from collections import deque
from nemo.indexing.links import LinkResolver


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

        queue = deque([[start]])

        while queue:

            path = queue.popleft()
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
        resolver = LinkResolver(index)
        for key in index:
            self.add_note(key)
        for key, note in index.items():
            for link in note.get("links", []):
                target = resolver.resolve(link, note.get("path", key))
                if target is not None and target != key:
                    self.add_edge(key, target)

    def connected_from(self, node):

        connected = []

        for source, targets in self.graph.items():

            if node in targets["connections"]:
                connected.append(source)

        return connected
