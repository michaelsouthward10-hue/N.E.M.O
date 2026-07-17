from nemo.graph.knowledge_graph import KnowledgeGraph
import json


class GraphService:

    def __init__(self):

        self.graph = KnowledgeGraph()

        with open("data/index.json", "r", encoding="utf-8") as file:
            index = json.load(file)

        self.graph.build(index)

    def find_relationship(self, source, target):

        return self.graph.find_path(source, target)