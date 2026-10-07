from nemo.graph.knowledge_graph import KnowledgeGraph
from nemo.parsers.entity_resolver import EntityResolver


class RelationshipService:

    def __init__(self, resolver=None, graph=None):

        self.resolver = resolver or EntityResolver()
        self.graph = graph or KnowledgeGraph()

        if not graph:
            self.graph.build(self.resolver.search.index)

    def find_relationship(self, source, target):

        source_note = self.resolver.resolve(source)
        target_note = self.resolver.resolve(target)

        if not source_note:
            return None

        if not target_note:
            return None

        source_name = source_note["title"]
        target_name = target_note["title"]

        return self.graph.find_path(
            source_name,
            target_name
        )