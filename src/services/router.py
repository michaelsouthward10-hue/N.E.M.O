class QuestionRouter:

    RELATIONSHIP_KEYWORDS = [
        "connected",
        "connection",
        "relationship",
        "related",
        "path",
        "between"
    ]

    def is_relationship_question(self, question):

        question = question.lower()

        return any(
            keyword in question
            for keyword in self.RELATIONSHIP_KEYWORDS
        )