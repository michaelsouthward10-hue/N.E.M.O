import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nemo.graph.knowledge_graph import KnowledgeGraph

graph = KnowledgeGraph()

graph.add_edge("Michael", "Lucifer")
graph.add_edge("Michael", "God")
graph.add_edge("Lucifer", "Hell")

print(graph.graph)

print()

print(graph.connected_to("Michael"))