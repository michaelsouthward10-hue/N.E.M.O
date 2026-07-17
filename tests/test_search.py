import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nemo.search.search_engine import SearchEngine

engine = SearchEngine()

results = engine.search_by_text("Michael")

print(results)