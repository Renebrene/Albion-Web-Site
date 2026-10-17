import re


class QuerySizeNormalizer:
    """
    Нормализует пользовательский размер.

    3*6 / 6*3 / 3х6 / 6x3 -> 6 X 3 Метр
    """

    PATTERN = re.compile(
        r"(?<!\d)"
        r"(\d+(?:[.,]\d+)?)"
        r"\s*(?:[xXхХ×*]|на)\s*"
        r"(\d+(?:[.,]\d+)?)"
        r"(?!\d)",
        re.IGNORECASE,
    )

    @classmethod
    def normalize(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        match = cls.PATTERN.search(value)

        if not match:
            return value

        first = float(match.group(1).replace(",", "."))
        second = float(match.group(2).replace(",", "."))

        first, second = sorted(
            (first, second),
            reverse=True,
        )

        def format_number(number: float) -> str:
            if number.is_integer():
                return str(int(number))

            # Site data stores decimal sizes with a comma («3,77 X 2,8 Метр»).
            return str(number).rstrip("0").rstrip(".").replace(".", ",")

        return (
            f"{format_number(first)} X "
            f"{format_number(second)} Метр"
        )
