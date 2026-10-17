from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchQuery:
    """
    Storage-independent structured search query.
    """

    city: str | None = None
    district: str | None = None
    address: str | None = None

    media_type: str | None = None
    size: str | None = None

    year: int | None = None
    month: int | None = None
    months: list[int] = field(default_factory=list)

    period_mode: str = "ANY"

    availability: str | None = None

    load_threshold: int | None = None
    max_load: int | None = None

    min_price: int | None = None
    max_price: int | None = None

    sort_by: str | None = None
    limit: int | None = None

    def __post_init__(self):
        if self.year is not None and not 2000 <= self.year <= 2100:
            raise ValueError("year должен быть от 2000 до 2100")

        if self.period_mode not in {"ANY", "ALL"}:
            raise ValueError(
                "period_mode должен быть ANY или ALL"
            )

        if self.month is not None and not 1 <= self.month <= 12:
            raise ValueError("month должен быть от 1 до 12")

        for month in self.months:
            if not 1 <= month <= 12:
                raise ValueError(f"Некорректный месяц: {month}")

        if self.month is not None and self.months:
            raise ValueError(
                "Нельзя одновременно задавать month и months"
            )

        if self.min_price is not None and self.min_price < 0:
            raise ValueError(
                "min_price не может быть отрицательным"
            )

        if self.max_price is not None and self.max_price < 0:
            raise ValueError(
                "max_price не может быть отрицательным"
            )

        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError(
                "min_price не может быть больше max_price"
            )

        if self.load_threshold is not None and not 0 <= self.load_threshold <= 100:
            raise ValueError(
                "load_threshold должен быть от 0 до 100"
            )

        if self.max_load is not None and not 0 <= self.max_load <= 100:
            raise ValueError(
                "max_load должен быть от 0 до 100"
            )

        if self.limit is not None and not 1 <= self.limit <= 1000:
            raise ValueError(
                "limit должен быть от 1 до 1000"
            )

    def get_months(self) -> list[int]:
        if self.month is not None:
            return [self.month]

        return list(self.months)

    def has_period(self) -> bool:
        return bool(
            self.month is not None or self.months
        )

    def debug(self) -> str:
        return (
            "SearchQuery("
            f"city={self.city!r}, "
            f"district={self.district!r}, "
            f"address={self.address!r}, "
            f"media_type={self.media_type!r}, "
            f"size={self.size!r}, "
            f"year={self.year!r}, "
            f"month={self.month!r}, "
            f"months={self.months!r}, "
            f"period_mode={self.period_mode!r}, "
            f"availability={self.availability!r}, "
            f"load_threshold={self.load_threshold!r}, "
            f"max_load={self.max_load!r}, "
            f"min_price={self.min_price!r}, "
            f"max_price={self.max_price!r}, "
            f"sort_by={self.sort_by!r}, "
            f"limit={self.limit!r}"
            ")"
        )

