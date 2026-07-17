import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nemo.services.router import QuestionRouter

router = QuestionRouter()

print(router.is_relationship_question(
    "How is Michael connected to Lucifer?"
))

print(router.is_relationship_question(
    "Who is Lucifer?"
))