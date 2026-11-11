from nemo.search.search_engine import SearchEngine


def test_search_finds_words_inside_natural_language_question(sample_index):
    search = SearchEngine()
    assert search.search_by_text("What do the notes say about Michael the archangel?")[0]["title"] == "Archangel Michael"
