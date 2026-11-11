from nemo.services.graph_service import GraphService


def test_graph_service_uses_index(sample_index):
    service = GraphService()
    assert service.find_relationship("Archangel Michael", "Lucifer")[-1] == "Lucifer"
