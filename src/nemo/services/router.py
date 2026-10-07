from nemo.parsers.question_parser import QuestionParser
from nemo.services.relationship_service import RelationshipService


class QuestionRouter:

    def __init__(self, parser=None, relationship_service=None):

        self.parser = parser or QuestionParser()
        self.relationship_service = (
            relationship_service or RelationshipService()
        )

    def route(self, question):

        parsed = self.parser.parse(question)

        if parsed.intent == "relationship":
            return "relationship"

        return "general"

    def handle(self, question):

        parsed = self.parser.parse(question)

        if parsed.intent == "relationship":

            if len(parsed.entities) < 2:
                return {
                    "type": "relationship",
                    "result": None,
                    "message": "I need two entities to find a relationship."
                }

            source = parsed.entities[0]
            target = parsed.entities[1]

            path = self.relationship_service.find_relationship(
                source,
                target
            )

            return {
                "type": "relationship",
                "result": path
            }

        return {
            "type": "general",
            "result": None
        }