from nemo.parsers.question_parser import QuestionParser
from nemo.services.relationship_service import RelationshipService
import re


class QuestionRouter:

    def __init__(self, parser=None, relationship_service=None):

        self.parser = parser or QuestionParser()
        self.relationship_service = (
            relationship_service or RelationshipService()
        )

    def route(self, question):

        parsed = self.parser.parse(question)

        wants_explanation = re.search(r"\b(why|explain|describe|compare|difference|differences|contrast|story)\b", question, re.IGNORECASE)
        if parsed.intent == "relationship" and len(parsed.entities) >= 2 and not wants_explanation:
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
