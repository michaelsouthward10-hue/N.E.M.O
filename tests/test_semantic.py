from nemo.search.semantic import SemanticSearch


class EmbedAI:
    endpoint = "http://localhost:11434"
    embedding_model = "test-embeddings"
    def __init__(self):
        self.calls = []

    def embed(self, texts, cancel_event=None):
        self.calls.append(texts)
        # Different wording shares meaning, with no matching keywords.
        return [[1.0, 0.0] if text in {"the sovereign died", "the king passed away"} else [0.0, 1.0] for text in texts]


def test_embedding_retrieval_matches_paraphrases_and_caches_documents(tmp_path):
    ai = EmbedAI()
    semantic = SemanticSearch(tmp_path / "vectors.sqlite3", ai)
    scores, warning = semantic.rank("the king passed away", ["the sovereign died", "fresh bread"])
    assert not warning
    assert scores[0][1] > scores[1][1]
    ai.calls.clear()
    semantic.rank("the king passed away", ["the sovereign died", "fresh bread"])
    assert ai.calls == [["the king passed away"]]
    semantic.clear()
    ai.calls.clear()
    semantic.rank("the king passed away", ["the sovereign died", "fresh bread"])
    assert len(ai.calls) == 2


def test_missing_embedding_model_returns_visible_fallback(tmp_path):
    ai = EmbedAI()
    def unavailable(*args):
        raise RuntimeError("Model missing")
    ai.embed = unavailable
    semantic = SemanticSearch(tmp_path / "vectors.sqlite3", ai)
    scores, warning = semantic.rank("question", ["text"])
    assert not scores and "unavailable" in warning
