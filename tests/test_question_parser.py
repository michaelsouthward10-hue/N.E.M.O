import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

print("Starting parser test...")

from nemo.parsers.question_parser import QuestionParser

print("Parser imported.")

parser = QuestionParser()

print("Parser created.")

question = parser.parse(
    "How is Michael connected to Lucifer?"
)

print("Question parsed.")

print(question.intent)
print(question.original)
print(question.entities)

print("Finished.")