from nemo.graph.knowledge_graph import KnowledgeGraph


def test_graph_connection():

    graph = KnowledgeGraph()

    graph.add_edge("Michael", "Lucifer")

    connections = graph.connected_to("Michael")

    assert "Lucifer" in connections


def test_graph_path():

    graph = KnowledgeGraph()

    graph.add_edge("Michael", "God")
    graph.add_edge("God", "Lucifer")

    path = graph.find_path("Michael", "Lucifer")

    assert path == [
        "Michael",
        "God",
        "Lucifer"
    ]