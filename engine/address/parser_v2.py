import re
from dataclasses import dataclass, field
from typing import Optional

from engine.address.root_parser import AddressRootParser


@dataclass
class AddressObject:
    """
    Один самостоятельный адресный объект.

    Например:

        Братский пер. 16

    это:

        street = "братский"
        roots  = ["братск"]
        house  = "16"
    """

    street: Optional[str] = None
    street_roots: list[str] = field(default_factory=list)
    house_number: Optional[str] = None
    house_components: list[str] = field(default_factory=list)


@dataclass
class ParsedAddress:
    """
    Полный разобранный адрес.

    Составной адрес хранится как список объектов.

        Братский пер. 16 / Московская ул. 12

    превращается в:

        objects[0] = Братский + 16
        objects[1] = Московская + 12
    """

    objects: list[AddressObject] = field(default_factory=list)

    # ---------------------------------------------------------
    # Совместимые свойства для одиночного адреса
    # ---------------------------------------------------------

    @property
    def street(self) -> Optional[str]:
        if not self.objects:
            return None
        return self.objects[0].street

    @property
    def street_roots(self) -> list[str]:
        if not self.objects:
            return []
        return self.objects[0].street_roots

    @property
    def house_number(self) -> Optional[str]:
        if not self.objects:
            return None
        return self.objects[0].house_number

    # ---------------------------------------------------------
    # Все улицы / корни / номера
    # ---------------------------------------------------------

    @property
    def streets(self) -> list[str]:
        return [
            obj.street
            for obj in self.objects
            if obj.street
        ]

    @property
    def all_street_roots(self) -> list[str]:
        result = []

        for obj in self.objects:
            for root in obj.street_roots:
                if root not in result:
                    result.append(root)

        return result

    @property
    def house_numbers(self) -> list[str]:
        return [
            obj.house_number
            for obj in self.objects
            if obj.house_number
        ]

    @property
    def all_house_components(self) -> list[str]:
        result = []

        for obj in self.objects:
            for component in obj.house_components:
                if component not in result:
                    result.append(component)

        return result


class AddressParserV2:

    root_parser = AddressRootParser()

    STREET_TYPES = {
        "ул",
        "улица",
        "пр",
        "проспект",
        "пр-кт",
        "пркт",
        "пер",
        "переулок",
        "бул",
        "бульвар",
        "ш",
        "шоссе",
        "наб",
        "набережная",
        "пл",
        "площадь",
        "туп",
        "тупик",
        "ал",
        "аллея",
    }

    # ---------------------------------------------------------
    # Нормализация
    # ---------------------------------------------------------

    @staticmethod
    def normalize(text: str) -> str:

        text = str(text or "").lower()

        text = text.replace("ё", "е")

        text = text.translate(
            str.maketrans({
                "a": "а",
                "e": "е",
                "o": "о",
                "p": "р",
                "c": "с",
                "x": "х",
                "y": "у",
                "k": "к",
                "m": "м",
                "t": "т",
                "b": "в",
            })
        )

        text = re.sub(
            r"[,.()]+",
            " ",
            text,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ---------------------------------------------------------
    # Номер дома
    # ---------------------------------------------------------

    @staticmethod
    def is_house_number(token: str) -> bool:

        # 1-й / 2-я / 3-е / 4-и
        # являются частью названия улицы.
        if re.fullmatch(
            r"\d+-(й|я|е|и)",
            token,
        ):
            return False

        return bool(
            re.fullmatch(
                r"""
                \d+[а-яa-z]?
                (?:
                    [-/]
                    (?:
                        \d+[а-яa-z]?
                        |
                        [а-яa-z]
                    )
                )*
                """,
                token,
                re.IGNORECASE | re.VERBOSE,
            )
        )

    # ---------------------------------------------------------
    # Число внутри названия
    # ---------------------------------------------------------

    @staticmethod
    def is_ordinal(token: str) -> bool:

        return bool(
            re.fullmatch(
                r"\d+-(й|я|е|и)",
                token,
            )
        )

    @staticmethod
    def is_compound_word_with_digits(token: str) -> bool:

        if not any(
            ch.isdigit()
            for ch in token
        ):
            return False

        return bool(
            re.search(
                r"\d+[а-яa-z]",
                token,
                re.IGNORECASE,
            )
        )

    # ---------------------------------------------------------
    # Поиск номера дома
    # ---------------------------------------------------------

    @classmethod
    def find_house_index(
        cls,
        tokens: list[str],
    ) -> Optional[int]:

        candidates = []

        positional_markers = {
            "п",
            "позиция",
        }

        for i, token in enumerate(tokens):

            if cls.is_ordinal(token):
                continue

            if not cls.is_house_number(token):
                continue

            # п. 1 / позиция 1 — не номер дома.
            if (
                i > 0
                and tokens[i - 1] in positional_markers
            ):
                continue

            candidates.append(i)

        if not candidates:
            return None

        # Ищем номер справа налево.
        #
        # Это важно для:
        #
        #   40 лет победы 113
        #
        # Здесь 40 НЕ дом,
        # дом = 113.
        for index in reversed(candidates):

            before = tokens[:index]

            if not before:
                continue

            after = tokens[index + 1:]

            if not after:
                return index

            # Отдельная буква после номера:
            #
            # 147 а
            # 32 б
            #
            if all(
                re.fullmatch(
                    r"[а-яa-z]",
                    x,
                    re.IGNORECASE,
                )
                for x in after
            ):
                return index

        return candidates[-1]

    # ---------------------------------------------------------
    # Компоненты номера дома
    # ---------------------------------------------------------

    @staticmethod
    def parse_house_components(
        house: Optional[str],
    ) -> list[str]:

        if not house:
            return []

        house = house.lower()

        # 10-12 / 10а-12б
        if "-" in house:
            parts = house.split("-")

            numbers = []
            letters = []

            for part in parts:
                match = re.fullmatch(
                    r"(\d+)([а-яa-z]?)",
                    part,
                    re.IGNORECASE,
                )

                if not match:
                    continue

                number, letter = match.groups()

                numbers.append(number)

                if letter:
                    letters.append(letter)

            return numbers + letters

        # 147/1 / 147а/1 / 147б/1
        if "/" in house:
            parts = house.split("/")

            result = []

            for part in parts:
                match = re.fullmatch(
                    r"(\d+)([а-яa-z]?)",
                    part,
                    re.IGNORECASE,
                )

                if not match:
                    continue

                number, letter = match.groups()

                result.append(number)

                if letter:
                    result.append(letter)

            return result

        # 147 / 147а
        match = re.fullmatch(
            r"(\d+)([а-яa-z]?)",
            house,
            re.IGNORECASE,
        )

        if not match:
            return [house]

        number, letter = match.groups()

        result = [number]

        if letter:
            result.append(letter)

        return result

    # ---------------------------------------------------------
    # Разбор одной части
    # ---------------------------------------------------------

    @classmethod
    def parse_part(
        cls,
        part: str,
    ) -> AddressObject:

        # Служебное описание в скобках не является
        # структурной частью адреса.
        part = re.sub(
            r"\([^)]*\)",
            " ",
            str(part or ""),
        )

        text = cls.normalize(part)

        if not text:
            return AddressObject()

        tokens = text.split()

        # Известный служебный хвост.
        while tokens and tokens[-1] in {
            "роллер",
        }:
            tokens.pop()

        if not tokens:
            return AddressObject()

        house_index = cls.find_house_index(
            tokens
        )

        if house_index is None:

            street_tokens = tokens
            house = None

        else:

            street_tokens = tokens[:house_index]

            house = tokens[house_index]

            # 147 а -> 147а
            if (
                house_index + 1 < len(tokens)
                and re.fullmatch(
                    r"[а-яa-z]",
                    tokens[house_index + 1],
                    re.IGNORECASE,
                )
                and tokens[house_index + 1] not in {
                    "в",
                    "п",
                    "с",
                }
            ):
                house += tokens[
                    house_index + 1
                ]

        house_components = cls.parse_house_components(
            house
        )

        # -----------------------------------------------------
        # Убираем тип улицы.
        # -----------------------------------------------------

        clean = []

        for token in street_tokens:

            if token in cls.STREET_TYPES:
                continue

            clean.append(token)

        if not clean:

            return AddressObject(
                street=None,
                street_roots=[],
                house_number=house,
                house_components=house_components,
            )

        street = " ".join(clean)

        roots = []

        for token in clean:

            # 1-й Конной Армии
            #
            # 1-й не является корнем.
            if cls.is_ordinal(token):
                continue

            root = cls.root_parser.root(token)

            if (
                root
                and root not in roots
            ):
                roots.append(root)

        return AddressObject(
            street=street,
            street_roots=roots,
            house_number=house,
            house_components=house_components,
        )

    # ---------------------------------------------------------
    # Полный адрес
    # ---------------------------------------------------------

    @classmethod
    def parse(
        cls,
        address: str,
    ):
        """
        Полный разбор адреса.

        Адрес может содержать несколько самостоятельных
        адресных объектов:

            Братский пер. 16 / Московская ул. 12

            Ростовский въезд - Сарматская

            Победы революции / Дачная

        Разделителями объектов считаются:

            /
            - с пробелами вокруг
            – с пробелами вокруг
            — с пробелами вокруг

        При этом номера домов:

            288-290
            126/1

        НЕ разделяются.
        """

        # Удаляем служебные комментарии в скобках
        # ДО нормализации, иначе скобки исчезнут и
        # содержимое станет частью адреса.
        address = re.sub(
            r"\([^)]*\)",
            " ",
            str(address or ""),
        )

        text = cls.normalize(address)

        if not text:
            return ParsedAddress()

        # -----------------------------------------------------
        # Разделяем только настоящие разделители объектов.
        #
        # ВАЖНО:
        #
        #   288-290  -> НЕ разделяем
        #   126/1    -> НЕ разделяем
        #
        # Поэтому:
        #
        #   "/" разделяем только если это не часть номера
        #   "-" / "–" / "—" разделяем только когда вокруг
        #   есть пробелы.
        # -----------------------------------------------------

        parts = []
        current = []

        tokens = text.split()

        for token in tokens:

            # 126/1, 147а/1 — составной НОМЕР.
            if "/" in token and re.fullmatch(
                r"\d+[а-яa-z]?(?:/\d+[а-яa-z]?)+",
                token,
                re.IGNORECASE,
            ):
                current.append(token)
                continue

            # '/' между адресными объектами.
            if token == "/":
                if current:
                    parts.append(" ".join(current))
                    current = []
                continue

            # '-' / '–' / '—' между адресными объектами.
            if token in {"-", "–", "—"}:
                if current:
                    parts.append(" ".join(current))
                    current = []
                continue

            # 249б/сызранова:
            # если slash находится внутри токена,
            # но это НЕ номер — это разделитель объектов.
            if "/" in token:
                left, right = token.split("/", 1)

                if left:
                    current.append(left)

                if current:
                    parts.append(" ".join(current))
                    current = []

                if right:
                    current.append(right)

                continue

            current.append(token)

        if current:
            parts.append(" ".join(current))

        parsed_parts = []

        for part in parts:

            part = part.strip()

            if not part:
                continue

            parsed = cls.parse_part(part)

            if parsed.street or parsed.house_number:
                parsed_parts.append(parsed)

        if not parsed_parts:
            return ParsedAddress()

        # -----------------------------------------------------
        # НОВАЯ МОДЕЛЬ:
        #
        # Возвращаем все самостоятельные адресные объекты.
        # -----------------------------------------------------

        # Все самостоятельные адресные объекты.
        #
        # Первый объект автоматически доступен через
        # совместимые properties:
        #
        #   result.street
        #   result.street_roots
        #   result.house_number
        #
        # Все объекты:
        #
        #   result.objects
        #
        return ParsedAddress(
            objects=parsed_parts
        )


# =============================================================
