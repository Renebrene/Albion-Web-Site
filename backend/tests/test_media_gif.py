"""Анимированный GIF не должен падать из-за отсутствующего import os."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from backend.services.media_service import _validate_image_header


def test_animated_gif_header_validation_uses_limits():
    frames = [
        Image.new("RGB", (2, 2), "red"),
        Image.new("RGB", (2, 2), "blue"),
    ]
    buffer = BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )

    image = Image.open(BytesIO(buffer.getvalue()))

    # Не должно быть NameError: os не импортирован.
    _validate_image_header(image)
