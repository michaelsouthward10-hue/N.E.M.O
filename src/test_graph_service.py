print("Starting test...")

from services.graph_service import GraphService

graph = GraphService()

print(f"Number of nodes: {len(graph.graph.graph)}")
print()

print("First 20 node names:")

for node in list(graph.graph.graph.keys())[:20]:
    print(node)