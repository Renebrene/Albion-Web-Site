"""Форматы вариантов изображений: card/thumb — WebP, large — JPEG."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from backend.services.media_service import _build_static_variants


def test_card_and_thumb_are_webp_large_stays_jpeg():
    image = Image.new("RGB", (1200, 800), "#4677a8")

    variants = _build_static_variants(image, preserve_png=False)

    assert variants["large"][1] == "image/jpeg"
    assert variants["large"][2] == ".jpg"

    # Карточные варианты — WebP: экономия ~21–29% при том же SSIM.
    assert variants["card"][1] == "image/webp"
    assert variants["card"][2] == ".webp"
    assert variants["thumb"][1] == "image/webp"
    assert variants["thumb"][2] == ".webp"

    # Все три варианта реально закодированы.
    assert all(data for data, _mime, _ext in variants.values())

    # Превью — 640px по длинной стороне (2× ширины карточки).
    with Image.open(BytesIO(variants["thumb"][0])) as thumb:
        assert max(thumb.size) == 640


def test_png_with_alpha_keeps_png():
    image = Image.new("RGBA", (600, 400), (255, 0, 0, 128))

    variants = _build_static_variants(image, preserve_png=True)

    assert all(mime == "image/png" for _data, mime, _ext in variants.values())
