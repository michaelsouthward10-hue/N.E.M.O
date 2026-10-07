from nemo.parsers.question_parser import QuestionParser


def test_relationship_question():

    parser = QuestionParser()

    question = parser.parse(
        "How is Michael connected to Lucifer?"
    )

    assert question.intent == "relationship"
    assert "Michael" in question.entities
    assert "Lucifer" in question.entities


def test_general_question():

    parser = QuestionParser()

    question = parser.parse(
        "Who is Michael?"
    )

    assert question.intent == "general"
    assert "Michael" in question.entities

def test_extract_relationship_entities():

    parser = QuestionParser()

    question = parser.parse(
        "How is Michael connected to Lucifer?"
    )

    assert question.intent == "relationship"
    assert question.entities == [
        "Michael",
        "Lucifer"
    ]

def test_extract_multiword_entity():

    parser = QuestionParser()

    question = parser.parse(
        "How is Archangel Michael connected to Lucifer?"
    )

    assert question.entities == [
        "Archangel Michael",
        "Lucifer"
    ]