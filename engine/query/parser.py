from __future__ import annotations

import re
from dataclasses import dataclass

from engine.address.parser_v2 import AddressParserV2
from engine.dictionary.synonym_dictionary import SynonymDictionary
from engine.query.query import SearchQuery
from engine.size.normalizer import QuerySizeNormalizer


@dataclass
class ParseResult:
    query: SearchQuery
    clarification: str | None = None


class QueryParser:
    """
    Детерминированный parser пользовательского запроса.

    Не зависит от storage/database.

    Распознаёт:
      - город;
      - район;
      - адрес;
      - тип конструкции;
      - статику / динамику;
      - размер;
      - месяц / несколько месяцев;
      - диапазон месяцев;
      - год;
      - FREE;
      - цену;
      - сортировку;
      - limit.
    """

    MONTHS = {
        1: ["январь", "января", "январе"],
        2: ["февраль", "февраля", "феврале"],
        3: ["март", "марта", "марте"],
        4: ["апрель", "апреля", "апреле"],
        5: ["май", "мая", "мае"],
        6: ["июнь", "июня", "июне"],
        7: ["июль", "июля", "июле"],
        8: ["август", "августа", "августе"],
        9: ["сентябрь", "сентября", "сентябре"],
        10: ["октябрь", "октября", "октябре"],
        11: ["ноябрь", "ноября", "ноябре"],
        12: ["декабрь", "декабря", "декабре"],
    }

    DISTRICTS = {
        "советский": (
            "советский",
            "советском",
            "советского",
            "советскому",
            "советским",
        ),
        "пролетарский": (
            "пролетарский",
            "пролетарском",
            "пролетарского",
            "пролетарскому",
            "пролетарским",
        ),
        "октябрьский": (
            "октябрьский",
            "октябрьском",
            "октябрьского",
            "октябрьскому",
            "октябрьским",
        ),
        "первомайский": (
            "первомайский",
            "первомайском",
            "первомайского",
            "первомайскому",
            "первомайским",
        ),
        "кировский": (
            "кировский",
            "кировском",
            "кировского",
            "кировскому",
            "кировским",
        ),
        "ленинский": (
            "ленинский",
            "ленинском",
            "ленинского",
            "ленинскому",
            "ленинским",
        ),
        "железнодорожный": (
            "железнодорожный",
            "железнодорожном",
            "железнодорожного",
            "железнодорожному",
            "железнодорожным",
        ),
    }

    ADDRESS_STOP_WORDS = (
        "в январ",
        "в феврал",
        "в март",
        "в апрел",
        "в ма",
        "в июн",
        "в июл",
        "в август",
        "в сентябр",
        "в октябр",
        "в ноябр",
        "в декабр",
    )

    def __init__(self, dictionary: SynonymDictionary):
        self.dictionary = dictionary
        self.address_parser = AddressParserV2()

    @staticmethod
    def _normalize(text: str) -> str:
        text = str(text).strip().lower().replace("ё", "е")
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _contains_alias(
        text: str,
        alias: str,
        allow_inflection: bool = True,
    ) -> bool:
        alias = alias.strip()

        if not alias:
            return False

        escaped = re.escape(alias)

        exact_pattern = (
            r"(?<!\w)" + escaped + r"(?!\w)"
        )

        if re.search(
            exact_pattern,
            text,
            re.IGNORECASE,
        ):
            return True

        if not allow_inflection:
            return False

        if " " in alias or "/" in alias:
            return False

        endings = (
            "а", "у", "е", "ы", "и",
            "ом", "ем", "ой", "ей",
            "ов", "ев", "ам", "ям",
            "ах", "ях", "ою", "ею",
        )

        endings_pattern = "|".join(
            re.escape(ending)
            for ending in endings
        )

        inflected_pattern = (
            r"(?<!\w)"
            + escaped
            + r"(?:"
            + endings_pattern
            + r")"
            + r"(?!\w)"
        )

        return re.search(
            inflected_pattern,
            text,
            re.IGNORECASE,
        ) is not None

    def _find_from_map(
        self,
        text: str,
        mapping: dict[str, str],
    ) -> str | None:
        matches = []

        for alias, canonical in mapping.items():
            if self._contains_alias(text, alias):
                matches.append((len(alias), canonical))

        if not matches:
            return None

        matches.sort(key=lambda item: -item[0])
        return matches[0][1]

    def _find_type_in_text(self, text: str) -> str | None:
        return self._find_from_map(
            text,
            self.dictionary.type_map,
        )

    def _find_city_in_text(self, text: str) -> str | None:
        return self._find_from_map(
            text,
            self.dictionary.city_map,
        )

    def _find_keyword_in_text(self, text: str) -> str | None:
        return self._find_from_map(
            text,
            self.dictionary.keyword_map,
        )

    def _find_district_in_text(self, text: str) -> str | None:
        matches = []

        for canonical, aliases in self.DISTRICTS.items():
            for alias in aliases:
                if self._contains_alias(
                    text,
                    alias,
                    allow_inflection=False,
                ):
                    matches.append(
                        (len(alias), canonical)
                    )

        if not matches:
            return None

        matches.sort(key=lambda item: -item[0])
        return matches[0][1]

    def _find_address_in_text(
        self,
        text: str,
    ) -> str | None:
        """
        Ищет адрес в запросе.

        Поддерживает:
          - явные конструкции "по адресу ...";
          - "адресе ...";
          - "на ...";
          - специальный адрес 40-летия Победы;
          - неявные адреса вида "Таганрогская 147";
          - составные адреса;
          - диапазоны домов;
          - номера с буквами и slash-компонентами.

        Важный принцип:
        тип конструкции / город / служебные слова не должны
        становиться частью адреса.
        """

        explicit_candidates = []

        explicit_patterns = [
            r"\bпо\s+адресу\s+(.+?)(?=$|,|\s+в\s+(?:январ|феврал|март|апрел|ма[ея]|июн|июл|август|сентябр|октябр|ноябр|декабр))",
            r"\bадрес(?:е|ом)?\s+(.+?)(?=$|,|\s+в\s+(?:январ|феврал|март|апрел|ма[ея]|июн|июл|август|сентябр|октябр|ноябр|декабр))",
            r"\bна\s+(.+?)(?=$|,|\s+в\s+(?:январ|феврал|март|апрел|ма[ея]|июн|июл|август|сентябр|октябр|ноябр|декабр))",
        ]

        for pattern in explicit_patterns:
            for match in re.finditer(
                pattern,
                text,
                re.IGNORECASE,
            ):
                candidate = match.group(1).strip(
                    " ,.;:!?()"
                )

                if candidate:
                    explicit_candidates.append(
                        (
                            len(candidate),
                            match.start(1),
                            candidate,
                        )
                    )

        # Специальный случай:
        # "40 Лет Победы 146А"
        special_pattern = re.compile(
            r"\b"
            r"40[-\s]+лет(?:ия)?\s+победы"
            r"\s+\d+[а-яa-z]?"
            r"(?:/\d+[а-яa-z]?)?"
            r"(?:\s*[-/]\s*\d+[а-яa-z]?)?"
            r"(?!\w)",
            re.IGNORECASE,
        )

        for match in special_pattern.finditer(text):
            explicit_candidates.append(
                (
                    len(match.group(0)),
                    match.start(),
                    match.group(0),
                )
            )

        valid_explicit = []

        for _, _, candidate in explicit_candidates:
            normalized = self._normalize(candidate)

            blocked = False

            for stop_word in self.ADDRESS_STOP_WORDS:
                if stop_word in normalized:
                    blocked = True
                    break

            if blocked:
                continue

            parsed = self.address_parser.parse(candidate)

            address_objects = [
                obj
                for obj in parsed.objects
                if obj.street and obj.house_number
            ]

            if not address_objects:
                continue

            valid_explicit.append(
                (
                    len(address_objects),
                    len(parsed.house_numbers),
                    len(candidate),
                    candidate,
                )
            )

        if valid_explicit:
            valid_explicit.sort(
                key=lambda item: (
                    -item[0],
                    -item[1],
                    item[2],
                )
            )
            return valid_explicit[0][3]

        # ------------------------------------------------------------
        # Неявный адрес.
        #
        # Ищем именно номер дома, а затем пытаемся расширить
        # фрагмент влево. Это принципиально важно:
        #
        #   "Ростов-на-Дону щит 40 Лет Победы 146А"
        #
        # не должен давать "щит 40".
        # ------------------------------------------------------------

        # Служебные числовые конструкции не являются адресом.
        # Иначе:
        #   "цена от 40000 до 46000"
        #   "первые 5"
        # могут ошибочно распознаваться как номера домов.
        address_text = re.sub(
            r"\bцена\s+(?:от\s+)?\d+(?:\s+до\s+\d+)?",
            " ",
            text,
            flags=re.IGNORECASE,
        )

        address_text = re.sub(
            r"\b(?:первые|первый|первых|первое|первую|лимит)\s+\d+\b",
            " ",
            address_text,
            flags=re.IGNORECASE,
        )

        address_text = re.sub(
            r"\bот\s+\d+\s+до\s+\d+\b",
            " ",
            address_text,
            flags=re.IGNORECASE,
        )

        # Числа выше 1000 в нашей предметной области
        # не являются номерами домов и должны считаться ценой.
        # Также исключаем явные денежные обозначения.
        address_text = re.sub(
            r"(?<!\w)\d[\d\s]*(?:тыс\.?|тысяч(?:а|и|у)?|руб(?:\.?|лей|ля|ль)?|₽)(?!\w)",
            " ",
            address_text,
            flags=re.IGNORECASE,
        )

        address_text = re.sub(
            r"(?<!\w)(?:до|от|дешевле|дороже|не\s+дороже)\s+\d[\d\s]*(?!\w)",
            " ",
            address_text,
            flags=re.IGNORECASE,
        )

        address_text = re.sub(
            r"(?<!\w)\d[\d\s]*(?=\b)(?!\s*(?:лет|год))",
            lambda match: " "
            if int(match.group(0).replace(" ", "")) > 1000
            else match.group(0),
            address_text,
        )

        tokens = address_text.split()

        house_pattern = re.compile(
            r"^\d+"
            r"(?:[а-яa-z])?"
            r"(?:"
            r"/\d+(?:[а-яa-z])?"
            r"|"
            r"-\d+(?:[а-яa-z])?"
            r")?$",
            re.IGNORECASE,
        )

        house_indexes = [
            index
            for index, token in enumerate(tokens)
            if house_pattern.match(
                token.strip(" ,.;:!?()")
            )
        ]

        implicit_candidates = []

        # Слова, которые не должны становиться частью адреса:
        # типы конструкций и служебные глаголы запроса.
        non_address_prefixes = {
            "щит",
            "биллборд",
            "билборд",
            "призматрон",
            "сити-формат",
            "ситиформат",
            "сити",
            "роллер",
            "сити-борд",
            "ситиборд",
            "скроллер",
            "пиллар",
            "пилларс",
            "пилар",
            "пиларс",
            "тумба",
            "видеоэкран",
            "диджитал",
            "телевизор",
            "статика",
            "динамика",
            # Служебные глаголы: «подбери 20» — это лимит, не адрес.
            "подбери",
            "подберите",
            "подобрать",
            "найди",
            "найдите",
            "покажи",
            "покажите",
            "выведи",
            "выведите",
            "выбери",
            "выберите",
            "дай",
            "дайте",
        }

        for house_index in house_indexes:
            start_min = max(
                0,
                house_index - 8,
            )

            for candidate_start in range(
                house_index - 1,
                start_min - 1,
                -1,
            ):
                for end_index in range(
                    house_index,
                    min(
                        len(tokens),
                        house_index + 9,
                    ),
                ):
                    candidate = " ".join(
                        tokens[
                            candidate_start:
                            end_index + 1
                        ]
                    ).strip(
                        " ,.;:!?()"
                    )

                    if not candidate:
                        continue

                    normalized = self._normalize(
                        candidate
                    )
                    normalized_tokens = normalized.split()

                    if not normalized_tokens:
                        continue

                    # Адрес не может содержать тип конструкции или
                    # служебный глагол запроса ("подбери 20", "видеоэкран 3").
                    if any(
                        token in non_address_prefixes
                        for token in normalized_tokens
                    ):
                        continue

                    # Не захватываем город как часть адреса.
                    if (
                        self._find_city_in_text(
                            normalized_tokens[0]
                        )
                        is not None
                    ):
                        continue

                    # Не позволяем адресу начинаться с месяца.
                    month_prefixes = tuple(
                        form[:4]
                        for forms in self.MONTHS.values()
                        for form in forms
                    )

                    month_token = normalized_tokens[0]

                    if any(
                        month_token.startswith(prefix)
                        for prefix in month_prefixes
                    ):
                        continue

                    # Месяц/год не является адресом.
                    if (
                        len(normalized_tokens) == 2
                        and normalized_tokens[0]
                        and normalized_tokens[1].isdigit()
                        and 1900 <= int(
                            normalized_tokens[1]
                        ) <= 2100
                    ):
                        continue

                    # Размер конструкции не может быть частью адреса.
                    #
                    # Например:
                    #   "6*3 ноябре 2026"
                    #
                    # Здесь 2026 ошибочно может выглядеть как номер дома
                    # для AddressParserV2, но 6*3 — это размер конструкции,
                    # а "ноябре 2026" — период запроса.
                    if self._find_size(normalized) is not None:
                        continue

                    # Отсекаем хвост запроса после адреса.
                    #
                    # "и"/"или" являются союзами периода, а не частью
                    # адреса:
                    #   "Троллейбусная 16В ... в октябре или ноябре"
                    #   "Троллейбусная 16В ... в октябре и ноябре"
                    #
                    # При этом "/" остаётся допустимым разделителем
                    # составного адреса.
                    blocked = False

                    for stop_word in self.ADDRESS_STOP_WORDS:
                        if stop_word in normalized:
                            blocked = True
                            break

                    if re.search(r"(?<!\w)(?:и|или)(?!\w)", normalized):
                        blocked = True

                    if blocked:
                        continue

                    parsed = self.address_parser.parse(
                        candidate
                    )

                    address_objects = [
                        obj
                        for obj in parsed.objects
                        if obj.street
                        and obj.house_number
                    ]

                    if not address_objects:
                        continue

                    # Кандидат должен содержать сам номер,
                    # возле которого строился фрагмент.
                    candidate_numbers = {
                        str(number).strip().lower()
                        for number in parsed.house_numbers
                    }

                    house_token = tokens[
                        house_index
                    ].strip(
                        " ,.;:!?()"
                    ).lower()

                    if house_token not in candidate_numbers:
                        continue

                    implicit_candidates.append(
                        (
                            len(address_objects),
                            len(parsed.house_numbers),
                            len(candidate),
                            candidate_start,
                            candidate,
                        )
                    )

        if implicit_candidates:
            implicit_candidates.sort(
                key=lambda item: (
                    -item[0],
                    -item[1],
                    item[2],
                    -item[3],
                )
            )

            return implicit_candidates[0][4]

        # Улица без номера дома: «на Привокзальной», «проспект Стачки».
        return self._find_street_only(text)

    def _find_street_only(self, text: str) -> str | None:
        """Улица без номера дома.

        Нужна для запросов вида «пиллар на Привокзальной», где номер
        дома не указан: адресный фильтр должен всё равно сузить выдачу.
        """
        candidates: list[str] = []

        # Явный маркер улицы + название: «ул. Ленина», «проспект Стачки».
        marker = (
            r"(?:ул\.|улиц\w*|проспект\w*|пр-?кт\w*|пр-?т\w*|переул\w*|"
            r"пер\.|шоссе|бульвар\w*|б-р|площад\w*|пл\.|проезд\w*|"
            r"набережн\w*|аллея)"
        )

        for match in re.finditer(
            marker + r"\s+([а-яё][а-яё-]{2,})",
            text,
            re.IGNORECASE,
        ):
            candidates.append(match.group(1))

        # Предлог + название улицы-прилагательного: «на Привокзальной».
        for match in re.finditer(
            r"\b(?:на|по|около|возле|у)\s+"
            r"([а-яё-]{4,}(?:ой|ая|ий|ую|ом|ым|ых|ская|ской|ское|ого|ому))",
            text,
            re.IGNORECASE,
        ):
            candidates.append(match.group(1))

        for candidate in candidates:
            normalized = self._normalize(candidate)

            if not normalized:
                continue

            # Служебные слова запроса улицей не являются.
            if re.search(
                r"загруж|дешев|стоимост|цен|наимен|наименее|сторон",
                normalized,
            ):
                continue

            # Улица не может совпадать с типом, городом или стоп-словом.
            if (
                self.dictionary.find_type(normalized)
                or self.dictionary.find_city(normalized)
                or self.dictionary.find_keyword(normalized)
            ):
                continue

            if any(
                stop_word in normalized
                for stop_word in self.ADDRESS_STOP_WORDS
            ):
                continue

            parsed = self.address_parser.parse(candidate)

            if not parsed.all_street_roots:
                continue

            return candidate

        return None

    def _expand_month_range(
        self,
        months: list[int],
        text: str,
    ) -> list[int]:
        normalized = self._normalize(text)

        range_pattern = re.compile(
            r"(?<!\w)"
            r"(январ\w*|феврал\w*|март\w*|апрел\w*|ма\w*|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)"
            r"\s*(?:-|–|—|до)\s*"
            r"(январ\w*|феврал\w*|март\w*|апрел\w*|ма\w*|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)",
            re.IGNORECASE,
        )

        match = range_pattern.search(normalized)

        if not match:
            return months

        def find_month(value: str) -> int | None:
            value = value.lower()

            for number, forms in self.MONTHS.items():
                for form in forms:
                    if value.startswith(
                        form.replace("ё", "е")[:3]
                    ):
                        return number

            return None

        start = find_month(match.group(1))
        end = find_month(match.group(2))

        if start is None or end is None:
            return months

        if start <= end:
            return list(range(start, end + 1))

        return months

    def _find_months(self, text: str) -> list[int]:
        found = []

        for month_number, forms in self.MONTHS.items():
            for form in forms:
                pattern = (
                    r"(?<!\w)"
                    + re.escape(form)
                    + r"(?!\w)"
                )

                if re.search(
                    pattern,
                    text,
                    re.IGNORECASE,
                ):
                    found.append(month_number)
                    break

        return self._expand_month_range(
            sorted(set(found)),
            text,
        )

    def _find_year(self, text: str) -> int | None:
        match = re.search(
            r"\b(20\d{2})\b",
            text,
        )

        if match:
            return int(match.group(1))

        # Год кампании определяется по активному импорту/настройке, а не
        # литералом: см. resolve_default_year() и repository.default_year().
        return None

    def _find_size(self, text: str) -> str | None:
        match = re.search(
            r"(?<!\d)"
            r"(\d+(?:[.,]\d+)?)"
            r"\s*[xх×*]"
            r"\s*"
            r"(\d+(?:[.,]\d+)?)"
            r"(?!\d)",
            text,
            re.IGNORECASE,
        )

        if not match:
            return None

        first = match.group(1).replace(",", ".")
        second = match.group(2).replace(",", ".")

        return f"{first} X {second}"

    def _find_limit(self, text: str) -> int | None:
        patterns = [
            r"\b(\d+)\s+наименее\s+загруж",
            r"\b(\d+)\s+наименьш\w*\s+загруж",
            r"\b(\d+)\s+самых\s+деш",
            r"\b(?:найди|покажи|выведи|подбери|выбери|дай)\s+(\d+)\b",
            r"\bпервые\s+(\d+)\b",
            r"\b(?:первый|первых|первое|первую)\s+(\d+)\b",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:
                return int(match.group(1))

        return None

    def _find_price_limits(
        self,
        text: str,
    ) -> tuple[int | None, int | None]:
        # Числа после "нагрузка/загрузка" относятся к нагрузке,
        # а не к цене. Убираем весь load-диапазон из price parsing.
        price_text = re.sub(
            r"(?:нагруз\w*|загруз\w*)\s+"
            r"(?:"
            r"от\s+\d{1,3}\s*%\s+до\s+\d{1,3}\s*%"
            r"|"
            r"(?:не\s+более|до|от)\s+\d{1,3}\s*%"
            r")",
            "",
            text,
            flags=re.IGNORECASE,
        )

        def parse_price_value(
            value: str,
            suffix: str | None,
        ) -> int:
            number = int(
                value.replace(" ", "")
            )

            if suffix and re.match(
                r"тыс",
                suffix,
                re.IGNORECASE,
            ):
                return number * 1000

            return number

        price_suffix = (
            r"(тыс\.?|тысяч(?:а|и|у)?|"
            r"руб(?:\.?|лей|ля|ль)?|₽)?"
        )

        max_match = re.search(
            r"(?:до|дешевле|не\s+дороже)\s*"
            r"(\d[\d\s]*)\s*"
            + price_suffix,
            price_text,
            re.IGNORECASE,
        )

        max_price = None

        if max_match:
            max_price = parse_price_value(
                max_match.group(1),
                max_match.group(2),
            )

        min_match = re.search(
            r"(?:от|дороже)\s*"
            r"(\d[\d\s]*)\s*"
            + price_suffix,
            price_text,
            re.IGNORECASE,
        )

        min_price = None

        if min_match:
            min_price = parse_price_value(
                min_match.group(1),
                min_match.group(2),
            )

        return min_price, max_price

    def _find_load_limits(
        self,
        text: str,
    ) -> tuple[int | None, int | None]:
        """
        Ищет ограничения по проценту загрузки.

        Поддерживает:
          - нагрузка до 30%
          - нагрузка не более 30%
          - нагрузка от 20%
          - нагрузка от 20% до 30%

        Границы включительные.
        """

        load_word = r"(?:нагруз\w*|загруз\w*)"

        max_match = re.search(
            r"(?:"
            + load_word
            + r"\s+(?:не\s+более|до)\s*"
            + r"(\d{1,3})\s*%"
            + r"|"
            + load_word
            + r"\s+от\s+\d{1,3}\s*%\s+до\s*"
            + r"(\d{1,3})\s*%"
            + r")",
            text,
            re.IGNORECASE,
        )

        max_load = None

        if max_match:
            max_load = int(
                max_match.group(1)
                or max_match.group(2)
            )

        min_match = re.search(
            load_word
            + r"\s+от\s*"
            + r"(\d{1,3})\s*%",
            text,
            re.IGNORECASE,
        )

        min_load = (
            int(min_match.group(1))
            if min_match
            else None
        )

        return min_load, max_load


    def _find_availability(self, text: str) -> str | None:
        if re.search(r"\bсвобод\w*", text):
            return "FREE"

        return None

    def _find_sort(self, text: str) -> str | None:
        if (
            re.search(r"наимене\w*\s+загруж", text)
            or re.search(r"наименьш\w*\s+загруж", text)
            or (
                re.search(r"минимальн", text)
                and re.search(r"загруз", text)
            )
        ):
            return "load_asc"

        if re.search(r"сам\w*\s+деш", text):
            return "price_asc"

        return None

    def _find_period_mode(self, text: str) -> str:
        normalized = self._normalize(text)

        if re.search(
            r"\b(?:все|каждый|каждом|одновременно|сразу)\b",
            normalized,
        ):
            return "ALL"

        if re.search(r"\bили\b", normalized):
            return "ANY"

        months = self._find_months(normalized)

        if len(months) > 1 and re.search(
            r"\bи\b",
            normalized,
        ):
            return "ALL"

        return "ANY"

    def parse(self, text: str) -> ParseResult:
        if not text or not str(text).strip():
            raise ValueError(
                "Поисковый запрос не может быть пустым"
            )

        text = self._normalize(text)

        city = self._find_city_in_text(text)
        district = self._find_district_in_text(text)
        address = self._find_address_in_text(text)

        media_type = self._find_type_in_text(text)
        keyword_type = self._find_keyword_in_text(text)

        if media_type is None:
            if re.search(r"\bстатик\w*\b", text):
                media_type = self.dictionary.find_keyword(
                    "статика"
                )
            elif re.search(r"\bдинамик\w*\b", text):
                media_type = self.dictionary.find_keyword(
                    "динамика"
                )
            elif keyword_type is not None:
                media_type = keyword_type

        raw_size = self._find_size(text)
        size = QuerySizeNormalizer.normalize(raw_size)

        months = self._find_months(text)
        year = self._find_year(text)

        month = None
        months_value = []

        if len(months) == 1:
            month = months[0]
        elif len(months) > 1:
            months_value = months

        availability = self._find_availability(text)
        sort_by = self._find_sort(text)
        limit = self._find_limit(text)

        min_load, max_load = self._find_load_limits(text)

        min_price, max_price = self._find_price_limits(text)

        period_mode = self._find_period_mode(text)

        query = SearchQuery(
            city=city,
            district=district,
            address=address,
            media_type=media_type,
            size=size,
            year=year,
            month=month,
            months=months_value,
            period_mode=period_mode,
            availability=availability,
            load_threshold=min_load,
            max_load=max_load,
            min_price=min_price,
            max_price=max_price,
            sort_by=sort_by,
            limit=limit,
        )

        if size is not None and media_type is None:
            return ParseResult(
                query=query,
                clarification=(
                    "Уточните тип конструкции: "
                    "статика или динамика?"
                ),
            )

        return ParseResult(
            query=query,
            clarification=None,
        )
