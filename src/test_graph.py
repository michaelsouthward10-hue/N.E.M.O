from graph.knowledge_graph import KnowledgeGraph

graph = KnowledgeGraph()

graph.add_edge("Michael", "Lucifer")
graph.add_edge("Michael", "God")
graph.add_edge("Lucifer", "Hell")

print(graph.graph)

print()

print(graph.connected_to("Michael"))