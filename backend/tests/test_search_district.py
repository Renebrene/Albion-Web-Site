"""Регрессия: SearchService больше не теряет query.district."""
from engine.query.query import SearchQuery
from engine.search.service import SearchService


class _Repo:
    def __init__(self):
        self.calls = []

    def find_by_filters_with_availability(self, **kwargs):
        self.calls.append(kwargs)
        return []

    def find_by_filters_any(self, **kwargs):
        self.calls.append(kwargs)
        return []

    def find_free(self, **kwargs):
        self.calls.append(kwargs)
        return []

    def find_free_any(self, **kwargs):
        self.calls.append(kwargs)
        return []


def test_district_passed_to_repository():
    repo = _Repo()
    service = SearchService(repo)

    service.search(SearchQuery(district="Октябрьский", year=2026))

    assert repo.calls[0]["district"] == "Октябрьский"


def test_district_passed_with_any_period():
    repo = _Repo()
    service = SearchService(repo)

    service.search(SearchQuery(district="Октябрьский", year=2026, months=[6, 7]))

    assert repo.calls[0]["district"] == "Октябрьский"


def test_district_none_is_harmless():
    repo = _Repo()
    service = SearchService(repo)

    service.search(SearchQuery(year=2026))

    assert repo.calls[0]["district"] is None
