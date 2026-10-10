import re
from dataclasses import dataclass


@dataclass(frozen=True)
class HouseNumberMatch:
    query: str
    candidate: str
    score: int
    exact: bool
    same_base: bool
    same_suffix: bool
    same_subnumber: bool


class HouseNumberMatcher:
    """
    Детерминированное сравнение номеров домов.

    Принцип:
      1. Точный номер -> максимальный score.
      2. Совпадает числовая база -> кандидат остаётся релевантным.
      3. Совпадает буква -> дополнительный score.
      4. Совпадает slash-part -> дополнительный score.
      5. Разные числовые базы -> 0.

    Это НЕ бинарный matcher.
    Внешний код может:
      - взять лучший вариант;
      - вывести несколько близких;
      - предложить уточнение.
    """

    _PATTERN = re.compile(
        r"^(?P<base>\d+)"
        r"(?P<suffix>[а-я])?"
        r"(?:(?:/(?P<subnumber>\d+)"
        r"(?P<subsuffix>[а-я])?)"
        r"|(?:-(?P<range_end>\d+)"
        r"(?P<range_suffix>[а-я])?))?$",
        re.IGNORECASE,
    )

    @staticmethod
    def _normalize(value: str) -> str:
        text = str(value or "").strip().lower()

        # Используем те же основные визуально похожие
        # кириллические/латинские замены, что и AddressParserV2.
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

        return text

    @classmethod
    def _parse(cls, value: str):
        value = cls._normalize(value)

        match = cls._PATTERN.fullmatch(value)

        if not match:
            return None

        return {
            "base": match.group("base"),
            "suffix": match.group("suffix"),
            "subnumber": match.group("subnumber"),
            "subsuffix": match.group("subsuffix"),
            "range_end": match.group("range_end"),
            "range_suffix": match.group("range_suffix"),
        }

    @classmethod
    def score(
        cls,
        query_number: str,
        candidate_number: str,
    ) -> HouseNumberMatch:

        query = cls._parse(query_number)
        candidate = cls._parse(candidate_number)

        if query is None or candidate is None:
            return HouseNumberMatch(
                query=str(query_number),
                candidate=str(candidate_number),
                score=0,
                exact=False,
                same_base=False,
                same_suffix=False,
                same_subnumber=False,
            )

        same_base = (
            query["base"] == candidate["base"]
        )

        if not same_base:
            return HouseNumberMatch(
                query=str(query_number),
                candidate=str(candidate_number),
                score=0,
                exact=False,
                same_base=False,
                same_suffix=False,
                same_subnumber=False,
            )

        query_normalized = cls._normalize(
            query_number
        )
        candidate_normalized = cls._normalize(
            candidate_number
        )

        exact = (
            query_normalized
            == candidate_normalized
        )

        query_is_range = (
            query["range_end"] is not None
        )

        candidate_is_range = (
            candidate["range_end"] is not None
        )

        # Диапазоны сравниваем только как диапазоны.
        # Это не обычный suffix-вариант.
        if query_is_range or candidate_is_range:
            if exact:
                return HouseNumberMatch(
                    query=str(query_number),
                    candidate=str(candidate_number),
                    score=100,
                    exact=True,
                    same_base=True,
                    same_suffix=(
                        query["suffix"] is not None
                        and candidate["suffix"] is not None
                    ),
                    same_subnumber=False,
                )

            # Число, попавшее в диапазон кандидата (или наоборот), — это
            # реальное совпадение: дом «105-107» содержит номер «105».
            query_start = int(query["base"])
            query_end = (
                int(query["range_end"])
                if query["range_end"] is not None
                else query_start
            )
            candidate_start = int(candidate["base"])
            candidate_end = (
                int(candidate["range_end"])
                if candidate["range_end"] is not None
                else candidate_start
            )

            overlaps = (
                query_start <= candidate_end
                and candidate_start <= query_end
            )

            if overlaps:
                return HouseNumberMatch(
                    query=str(query_number),
                    candidate=str(candidate_number),
                    score=80,
                    exact=False,
                    same_base=(query["base"] == candidate["base"]),
                    same_suffix=False,
                    same_subnumber=False,
                )

            return HouseNumberMatch(
                query=str(query_number),
                candidate=str(candidate_number),
                score=0,
                exact=False,
                same_base=(
                    query["base"] == candidate["base"]
                ),
                same_suffix=False,
                same_subnumber=False,
            )

        same_suffix = (
            query["suffix"] is not None
            and candidate["suffix"] is not None
            and query["suffix"]
            == candidate["suffix"]
        )

        same_subnumber = (
            query["subnumber"] is not None
            and candidate["subnumber"] is not None
            and query["subnumber"]
            == candidate["subnumber"]
        )

        # -----------------------------------------------------
        # Явно указанные компоненты должны совпадать.
        #
        # Если запрос содержит suffix:
        #   146А -> 146А       ✓
        #   146А -> 146А/1     ✓
        #   146А -> 146Б       ✗
        #   146А -> 146        ✗
        #
        # Если запрос содержит subnumber:
        #   59/101 -> 59/101       ✓
        #   59/101 -> 59А/101      ✓
        #   59/101 -> 59/102       ✗
        #
        # Более конкретный кандидат допустим, но другой
        # явно заданный компонент — нет.
        # -----------------------------------------------------

        if query["suffix"] is not None:
            if candidate["suffix"] != query["suffix"]:
                return HouseNumberMatch(
                    query=str(query_number),
                    candidate=str(candidate_number),
                    score=0,
                    exact=False,
                    same_base=True,
                    same_suffix=False,
                    same_subnumber=same_subnumber,
                )

        if query["subnumber"] is not None:
            if candidate["subnumber"] != query["subnumber"]:
                return HouseNumberMatch(
                    query=str(query_number),
                    candidate=str(candidate_number),
                    score=0,
                    exact=False,
                    same_base=True,
                    same_suffix=same_suffix,
                    same_subnumber=False,
                )

        # -----------------------------------------------------
        # Полное совпадение
        # -----------------------------------------------------

        if exact:
            return HouseNumberMatch(
                query=str(query_number),
                candidate=str(candidate_number),
                score=100,
                exact=True,
                same_base=True,
                same_suffix=(
                    query["suffix"] is not None
                    and candidate["suffix"] is not None
                ),
                same_subnumber=(
                    query["subnumber"] is not None
                    and candidate["subnumber"] is not None
                ),
            )

        # -----------------------------------------------------
        # Запрос только по base:
        #
        #   16 -> 16в
        #   16 -> 16/1
        #   16 -> 16в/1
        #
        # Такие варианты считаем близкими.
        # -----------------------------------------------------

        query_is_base_only = (
            query["suffix"] is None
            and query["subnumber"] is None
        )

        if query_is_base_only:
            return HouseNumberMatch(
                query=str(query_number),
                candidate=str(candidate_number),
                score=80,
                exact=False,
                same_base=True,
                same_suffix=False,
                same_subnumber=False,
            )

        # -----------------------------------------------------
        # Явно указана буква.
        # -----------------------------------------------------

        if (
            query["suffix"] is not None
            and same_suffix
        ):

            if (
                query["subnumber"] is not None
                and same_subnumber
            ):
                score = 95
            else:
                # Например:
                #   59а -> 59а/101
                score = 90

            return HouseNumberMatch(
                query=str(query_number),
                candidate=str(candidate_number),
                score=score,
                exact=False,
                same_base=True,
                same_suffix=True,
                same_subnumber=same_subnumber,
            )

        # -----------------------------------------------------
        # Явно указан slash-part.
        # -----------------------------------------------------

        if (
            query["subnumber"] is not None
            and same_subnumber
        ):
            return HouseNumberMatch(
                query=str(query_number),
                candidate=str(candidate_number),
                score=85,
                exact=False,
                same_base=True,
                same_suffix=same_suffix,
                same_subnumber=True,
            )

        # -----------------------------------------------------
        # Только base совпадает, но запрос был более точным.
        #
        # Например:
        #   16в -> 16
        #   59а/101 -> 59
        #   59а -> 59б
        # -----------------------------------------------------

        return HouseNumberMatch(
            query=str(query_number),
            candidate=str(candidate_number),
            score=60,
            exact=False,
            same_base=True,
            same_suffix=same_suffix,
            same_subnumber=same_subnumber,
        )

    @classmethod
    def best_match(
        cls,
        query_number: str,
        candidate_numbers: list[str],
    ) -> HouseNumberMatch | None:
        matches = [
            cls.score(query_number, candidate)
            for candidate in candidate_numbers
        ]

        matches = [
            match
            for match in matches
            if match.score > 0
        ]

        if not matches:
            return None

        return max(
            matches,
            key=lambda match: (
                match.score,
                int(match.exact),
                int(match.same_suffix),
                int(match.same_subnumber),
            ),
        )

    @classmethod
    def best_matches(
        cls,
        query_number: str,
        candidate_numbers: list[str],
        *,
        min_score: int = 60,
    ) -> list[HouseNumberMatch]:
        matches = [
            cls.score(query_number, candidate)
            for candidate in candidate_numbers
        ]

        matches = [
            match
            for match in matches
            if match.score >= min_score
        ]

        return sorted(
            matches,
            key=lambda match: (
                -match.score,
                match.candidate,
            ),
        )
