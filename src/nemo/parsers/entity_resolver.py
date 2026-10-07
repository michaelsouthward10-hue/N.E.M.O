from nemo.search.search_engine import SearchEngine


class EntityResolver:

    def __init__(self, search_engine=None):

        self.search = search_engine or SearchEngine()

    def resolve(self, entity):

        result = self.search.search_by_title(entity)

        if not result:
            return None

        return result