from __future__ import annotations

import pytest

from engine.dictionary.synonym_dictionary import SynonymDictionary

from backend.services import synonyms_service
from backend.tests.conftest import requires_db


def test_from_dict_rejects_alias_conflict():
    with pytest.raises(ValueError, match="Конфликт словаря"):
        SynonymDictionary.from_dict(
            {
                "types": {
                    "Щит": {"aliases": ["реклама"]},
                    "Пиллар": {"aliases": ["реклама"]},
                },
                "cities": {},
                "keywords": {},
            }
        )


def test_from_dict_rejects_broken_structure():
    with pytest.raises(ValueError):
        SynonymDictionary.from_dict({"types": [], "cities": {}, "keywords": {}})


def test_save_rejects_conflicting_aliases_without_db_write():
    with pytest.raises(ValueError, match="Конфликт словаря"):
        synonyms_service.save_synonyms(
            {
                "types": {
                    "Щит": {"aliases": ["дубль"]},
                    "Пиллар": {"aliases": ["дубль"]},
                },
                "cities": {},
                "keywords": {},
            }
        )


@requires_db
def test_synonyms_roundtrip_and_reset():
    try:
        saved = synonyms_service.save_synonyms(
            {
                "types": {"Щит": {"aliases": ["щит", "тестовый формат"]}},
                "cities": {"Ростов-на-Дону": {"aliases": ["ростов", "тестград"]}},
                "keywords": {"статика": "Щит"},
            }
        )

        assert saved["is_custom"] is True
        assert saved["dictionary"]["types"]["Щит"]["aliases"] == [
            "щит",
            "тестовый формат",
        ]

        dictionary, version = synonyms_service.load_active_dictionary()
        assert dictionary.find_type("тестовый формат") == "Щит"
        assert dictionary.find_city("тестград") == "Ростов-на-Дону"
        assert version != synonyms_service.PACKAGED_VERSION
    finally:
        synonyms_service.reset_synonyms()

    current = synonyms_service.get_synonyms()
    assert current["is_custom"] is False
    assert current["dictionary"] == synonyms_service.load_packaged_dictionary()
