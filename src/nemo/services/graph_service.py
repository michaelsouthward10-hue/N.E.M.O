from nemo.graph.knowledge_graph import KnowledgeGraph
from nemo.search.search_engine import SearchEngine


class GraphService:

    def __init__(self):

        self.graph = KnowledgeGraph()

        self.graph.build(SearchEngine().index)

    def find_relationship(self, source, target):

        return self.graph.find_path(source, target)
