from nemo.services.router import QuestionRouter


def test_relationship_route():

    router = QuestionRouter()

    result = router.route(
        "How is Michael connected to Lucifer?"
    )

    assert result == "relationship"


def test_general_route():

    router = QuestionRouter()

    result = router.route(
        "Who is Michael?"
    )

    assert result == "general"