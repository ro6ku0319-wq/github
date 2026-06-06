from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResolutionPreset:
    key: str
    label: str
    width: int
    height: int


DEFAULT_RESOLUTION_PRESET = "portrait_1080p"

RESOLUTION_PRESETS = {
    preset.key: preset
    for preset in (
        ResolutionPreset("portrait_1080p", "竖屏 1080p（1080×1920）", 1080, 1920),
        ResolutionPreset("landscape_1080p", "横屏 1080p（1920×1080）", 1920, 1080),
        ResolutionPreset("landscape_2k", "横屏 2K（2560×1440）", 2560, 1440),
        ResolutionPreset("portrait_2k", "竖屏 2K（1440×2560）", 1440, 2560),
    )
}


def get_resolution_preset(key: str) -> ResolutionPreset:
    try:
        return RESOLUTION_PRESETS[key]
    except KeyError as error:
        raise ValueError(f"未知输出分辨率预设: {key}") from error


def preset_key_for_size(width: int, height: int) -> str:
    for key, preset in RESOLUTION_PRESETS.items():
        if preset.width == width and preset.height == height:
            return key
    return DEFAULT_RESOLUTION_PRESET
