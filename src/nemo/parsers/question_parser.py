class Question:

    def __init__(
        self,
        intent="general",
        entities=None,
        original=""
    ):
        self.intent = intent
        self.entities = entities or []
        self.original = original


class QuestionParser:

    RELATIONSHIP_KEYWORDS = {
        "connected",
        "relationship",
        "related",
        "between",
        "path"
    }

    def parse(self, text):

        lower = text.lower()

        intent = "general"

        for keyword in self.RELATIONSHIP_KEYWORDS:
            if keyword in lower:
                intent = "relationship"
                break

        return Question(
            intent=intent,
            original=text
        )