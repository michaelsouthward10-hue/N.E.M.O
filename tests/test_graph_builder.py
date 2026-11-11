from nemo.graph.knowledge_graph import KnowledgeGraph


def test_graph_builds_resolved_links(sample_index):
    graph = KnowledgeGraph()
    graph.build(sample_index)
    assert graph.find_path("Archangel Michael", "Lucifer") == ["Archangel Michael", "God", "Lucifer"]
