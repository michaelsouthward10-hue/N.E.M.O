from nemo.services.router import QuestionRouter


def test_full_relationship_pipeline():

    router = QuestionRouter()

    result = router.handle(
        "How is Michael connected to Lucifer?"
    )

    assert result["type"] == "relationship"

    assert result["result"] is not None

    assert result["result"][0] == "Archangel Michael"

    assert result["result"][-1] == "Lucifer"