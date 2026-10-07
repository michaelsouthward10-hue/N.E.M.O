from nemo.constellation import ConstellationWindow


def make_map(index):
    constellation = ConstellationWindow.__new__(ConstellationWindow)
    constellation.index = index
    constellation.note_titles = sorted(
        {note.get("title", key) for key, note in index.items()},
        key=str.casefold,
    )
    constellation.title_lookup = {title.casefold(): title for title in constellation.note_titles}
    constellation.edges, constellation.neighbors = constellation._build_edges()
    return constellation


def test_constellation_resolves_alias_heading_and_folder_links():
    index = {
        "Athena": {"title": "Athena", "links": ["Pantheon/Athena.md"]},
        "Zeus": {"title": "Zeus", "path": "Pantheon/Zeus.md", "links": []},
        "Iliad": {
            "title": "Iliad",
            "links": ["Zeus|King of Olympus", "Athena#strategy"],
        },
    }
    constellation = make_map(index)

    assert constellation.neighbors["Iliad"] == {"Athena", "Zeus"}
    assert constellation.neighbors["Athena"] == {"Iliad"}
    assert constellation.neighbors["Zeus"] == {"Iliad"}


def test_constellation_traverses_the_selected_number_of_links():
    constellation = make_map(
        {
            "Athena": {"title": "Athena", "links": ["Odysseus"]},
            "Odysseus": {"title": "Odysseus", "links": ["Ithaca"]},
            "Ithaca": {"title": "Ithaca", "links": []},
        }
    )

    one_link, one_truncated = constellation._visible_levels("Athena", 1)
    two_links, two_truncated = constellation._visible_levels("Athena", 2)

    assert one_link == {"Athena": 0, "Odysseus": 1}
    assert two_links == {"Athena": 0, "Odysseus": 1, "Ithaca": 2}
    assert not one_truncated
    assert not two_truncated
