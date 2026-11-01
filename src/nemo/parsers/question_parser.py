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

    def __repr__(self):
        return (
            f"Question("
            f"intent='{self.intent}', "
            f"entities={self.entities}, "
            f"original='{self.original}'"
            f")"
        )


class QuestionParser:

    RELATIONSHIP_KEYWORDS = {
        "connected",
        "connection",
        "relationship",
        "related",
        "between",
        "path"
    }

    QUESTION_WORDS = {
        "who",
        "what",
        "where",
        "when",
        "why",
        "how",
        "is",
        "are",
        "the",
        "a",
        "an",
        "to",
        "of",
        "me",
        "tell",
        "about"
    }

    def parse(self, text):

        intent = self.detect_intent(text)
        entities = self.extract_entities(text)

        return Question(
            intent=intent,
            entities=entities,
            original=text
        )

    def detect_intent(self, text):

        lower = text.lower()

        for keyword in self.RELATIONSHIP_KEYWORDS:

            if keyword in lower:
                return "relationship"

        return "general"

    def extract_entities(self, text):

        words = text.replace("?", "").split()

        entities = []
        current_entity = []

        for word in words:

            clean = word.strip(".,!?")

            if not clean:
                continue

            if clean.lower() in self.QUESTION_WORDS:

                if current_entity:
                    entities.append(" ".join(current_entity))
                    current_entity = []

                continue

            if clean[0].isupper():

                current_entity.append(clean)

            else:

                if current_entity:
                    entities.append(" ".join(current_entity))
                    current_entity = []

        if current_entity:
            entities.append(" ".join(current_entity))

        return entities