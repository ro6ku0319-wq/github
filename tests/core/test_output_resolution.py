from __future__ import annotations

import pytest

from src.core.output_resolution import (
    DEFAULT_RESOLUTION_PRESET,
    RESOLUTION_PRESETS,
    get_resolution_preset,
    preset_key_for_size,
)


def test_resolution_presets_include_supported_landscape_and_portrait_sizes() -> None:
    assert DEFAULT_RESOLUTION_PRESET == "portrait_1080p"
    assert {
        key: (preset.width, preset.height)
        for key, preset in RESOLUTION_PRESETS.items()
    } == {
        "portrait_1080p": (1080, 1920),
        "landscape_1080p": (1920, 1080),
        "landscape_2k": (2560, 1440),
        "portrait_2k": (1440, 2560),
    }


def test_resolution_preset_can_be_found_by_dimensions() -> None:
    assert preset_key_for_size(2560, 1440) == "landscape_2k"
    assert preset_key_for_size(999, 777) == DEFAULT_RESOLUTION_PRESET


def test_unknown_resolution_preset_is_rejected() -> None:
    with pytest.raises(ValueError, match="未知输出分辨率预设"):
        get_resolution_preset("cinema_4k")
