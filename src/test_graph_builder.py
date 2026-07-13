import json

from graph.knowledge_graph import KnowledgeGraph

with open("data/index.json", "r", encoding="utf-8") as file:
    index = json.load(file)

graph = KnowledgeGraph()

graph.build(index)

print(graph.connected_to("Archangel Michael"))