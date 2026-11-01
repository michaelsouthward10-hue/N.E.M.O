from nemo.services.relationship_service import RelationshipService


def test_relationship_service():

    service = RelationshipService()

    result = service.find_relationship(
        "Michael",
        "Lucifer"
    )

    assert result is not None
    assert result[0] == "Archangel Michael"
    assert result[-1] == "Lucifer"