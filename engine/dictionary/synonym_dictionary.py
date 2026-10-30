import json
from pathlib import Path


class SynonymDictionary:
    """
    Storage-independent synonym dictionary.

    JSON schema:
      types
      cities
      keywords
    """

    CATEGORIES = {
        "types",
        "cities",
        "keywords",
    }

    def __init__(self, filename: str | Path | None = None):
        self.filename = Path(filename) if filename is not None else None
        self.data: dict = {}

        self.type_map: dict[str, str] = {}
        self.city_map: dict[str, str] = {}
        self.keyword_map: dict[str, str] = {}

        if self.filename is not None:
            self.load()

    @classmethod
    def from_dict(cls, data: dict) -> "SynonymDictionary":
        """Build a dictionary from an already parsed JSON object.

        Used by the admin editor: the payload is validated without writing
        a temporary file.
        """
        dictionary = cls()
        dictionary.load_data(data)
        return dictionary

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(
            str(value)
            .strip()
            .lower()
            .replace("ё", "е")
            .split()
        )

    def load(self):
        if not self.filename.exists():
            raise FileNotFoundError(
                f"Файл словаря не найден: {self.filename}"
            )

        with self.filename.open("r", encoding="utf-8") as file:
            data = json.load(file)

        self.load_data(data)

    def load_data(self, data: dict):
        if not isinstance(data, dict):
            raise ValueError("Словарь должен быть JSON-объектом")

        for category in self.CATEGORIES:
            value = data.get(category, {})
            if not isinstance(value, dict):
                raise ValueError(
                    f"Раздел словаря «{category}» должен быть объектом"
                )
            data[category] = value

        for category in ("types", "cities"):
            for canonical, config in data[category].items():
                if not isinstance(config, dict):
                    raise ValueError(
                        f"Запись словаря «{category}» / «{canonical}» "
                        "должна быть объектом"
                    )

                aliases = config.get("aliases", [])
                if not isinstance(aliases, list) or any(
                    not isinstance(alias, str) for alias in aliases
                ):
                    raise ValueError(
                        f"Поле aliases у «{canonical}» должно быть "
                        "списком строк"
                    )

        if any(
            not isinstance(value, str)
            for value in data["keywords"].values()
        ):
            raise ValueError(
                "Значения раздела keywords должны быть строками"
            )

        self.data = data

        for category in self.CATEGORIES:
            if category not in self.data:
                self.data[category] = {}

        self.type_map.clear()
        self.city_map.clear()
        self.keyword_map.clear()

        self._build_alias_map(
            self.data["types"],
            self.type_map,
        )
        self._build_alias_map(
            self.data["cities"],
            self.city_map,
        )
        self._build_keyword_map(
            self.data["keywords"],
            self.keyword_map,
        )

    def _build_alias_map(
        self,
        source: dict,
        target: dict[str, str],
    ):
        for canonical, config in source.items():
            self._set_mapping(
                target,
                self._normalize(canonical),
                canonical,
            )

            for alias in config.get("aliases", []):
                self._set_mapping(
                    target,
                    self._normalize(alias),
                    canonical,
                )

    def _build_keyword_map(
        self,
        source: dict,
        target: dict[str, str],
    ):
        for keyword, canonical in source.items():
            self._set_mapping(
                target,
                self._normalize(keyword),
                canonical,
            )

    @staticmethod
    def _set_mapping(
        target: dict[str, str],
        key: str,
        canonical: str,
    ):
        existing = target.get(key)

        if existing is not None and existing != canonical:
            raise ValueError(
                "Конфликт словаря: "
                f"{key!r} -> {existing!r} / {canonical!r}"
            )

        target[key] = canonical

    def find_type(self, value: str) -> str | None:
        return self.type_map.get(self._normalize(value))

    def find_city(self, value: str) -> str | None:
        return self.city_map.get(self._normalize(value))

    def find_keyword(self, value: str) -> str | None:
        return self.keyword_map.get(self._normalize(value))

    def is_type(self, value: str) -> bool:
        return self.find_type(value) is not None

    def is_city(self, value: str) -> bool:
        return self.find_city(value) is not None

    def is_keyword(self, value: str) -> bool:
        return self.find_keyword(value) is not None

    def get_types(self) -> list[str]:
        return list(self.data["types"].keys())

    def get_cities(self) -> list[str]:
        return list(self.data["cities"].keys())

    def get_keywords(self) -> dict[str, str]:
        return dict(self.data["keywords"])
