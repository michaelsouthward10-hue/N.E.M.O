from nemo.parsers.entity_resolver import EntityResolver


def test_resolve_existing_entity():

    resolver = EntityResolver()

    result = resolver.resolve("Michael")

    assert result is not None


def test_resolve_missing_entity():

    resolver = EntityResolver()

    result = resolver.resolve("ThisCharacterDefinitelyDoesNotExist")

    assert result is None