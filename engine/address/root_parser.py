import re


class AddressRootParser:

    MIN_ROOT_LENGTH = 3

    # Удаляем только конечные окончания.
    #
    # НИЧЕГО НЕ ДОБАВЛЯЕМ.
    #
    # Например:
    #
    # Троллейбусная   -> троллейбусн
    # Орская          -> орск
    # Таганрогская    -> таганрогск
    # Александровская -> александровск
    # Малиновского    -> малиновск
    #
    ENDINGS = (
        "иями",
        "ями",
        "ами",

        "ого",
        "ему",
        "ому",
        "ыми",
        "ими",
        "ых",
        "их",

        "ая",
        "яя",
        "ую",
        "юю",
        "ое",
        "ее",
        "ые",
        "ие",
        "ой",
        "ый",
        "ий",
        "ай",

        "ою",
        "ею",

        "ей",

        "ов",
        "ев",

        "ам",
        "ям",
        "ах",
        "ях",

        "ом",
        "ем",

        "ы",
        "и",

        "а",
        "я",

        "у",
        "ю",

        "о",
        "е",

        "ь",
    )

    @classmethod
    def normalize(cls, word: str) -> str:
        word = str(word or "").lower().replace("ё", "е")

        return re.sub(
            r"[^а-яa-z]",
            "",
            word,
        )

    @classmethod
    def root(cls, word: str) -> str:

        word = cls.normalize(word)

        if not word:
            return ""

        protected = {
            "радио",
            "метро",
            "кино",
            "шоссе",
            "какао",
            "пальто",
            "домино",
        }

        if word in protected:
            return word

        for ending in sorted(
            cls.ENDINGS,
            key=len,
            reverse=True,
        ):
            if not word.endswith(ending):
                continue

            base = word[:-len(ending)]

            if len(base) >= cls.MIN_ROOT_LENGTH:
                return base

        return word

    @classmethod
    def parse_words(
        cls,
        words: list[str],
    ) -> list[str]:

        result = []

        for word in words:

            root = cls.root(word)

            if root and root not in result:
                result.append(root)

        return result
