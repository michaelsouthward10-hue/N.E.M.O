from nemo.search.search_engine import SearchEngine


def test_missing_index_starts_empty(tmp_path):
    engine = SearchEngine()
    engine.index_path = tmp_path / "not-created-yet.json"

    assert engine.load_index() == {}
