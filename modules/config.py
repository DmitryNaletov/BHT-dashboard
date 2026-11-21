# modules/config.py
import json
from pathlib import Path

_DEFAULT_SETTINGS = {
    "font_family": (
        "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', "
        "Roboto, 'Helvetica Neue', Arial, sans-serif"
    ),
    "font_sizes": {
        "block_title": 30,
        "base": 16,
        "metric": 16,
        "axis_title": 16,
        "value_label": 16,
        "tooltip": 16,
        "axis_tick": 10,
        "interface": 14,
    },
    "mobile_scale": 0.9,
    "colors": {
        "text_light_theme": "#000000",
        "text_dark_theme": "#FFFFFF",
        "significance_positive": "#008000",
        "significance_negative": "#FF0000",
    },
}

_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.json"


def _load_settings():
    """Читает JSON и дополняет отсутствующие параметры значениями по умолчанию."""
    settings = {
        **_DEFAULT_SETTINGS,
        "font_sizes": dict(_DEFAULT_SETTINGS["font_sizes"]),
        "colors": dict(_DEFAULT_SETTINGS["colors"]),
    }

    try:
        with _SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
            loaded = json.load(settings_file)

        if isinstance(loaded, dict):
            settings.update({
                key: value
                for key, value in loaded.items()
                if key not in ("font_sizes", "colors")
            })

            if isinstance(loaded.get("font_sizes"), dict):
                settings["font_sizes"].update(loaded["font_sizes"])

            if isinstance(loaded.get("colors"), dict):
                settings["colors"].update(loaded["colors"])

    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as error:
        print(f"Не удалось прочитать {_SETTINGS_PATH}: {error}")

    return settings


SETTINGS = _load_settings()

# Совместимость с модулями, которые пока импортируют эти константы.
FONT_FAMILY = SETTINGS["font_family"]
FONT_PX = SETTINGS["font_sizes"]["base"]

# Временная совместимость. При унификации текста будем постепенно убирать GRAY.
GRAY = "#999999"


def get_font_size(name, is_mobile=False):
    """Возвращает размер шрифта из JSON с мобильным масштабом при необходимости."""
    size = SETTINGS["font_sizes"].get(
        name,
        SETTINGS["font_sizes"]["base"],
    )

    if is_mobile:
        size *= SETTINGS["mobile_scale"]

    return size


def get_text_color():
    """Цвет текста для текущей темы Streamlit."""
    try:
        import streamlit as st

        is_dark = st.get_option("theme.base") == "dark"
    except Exception:
        is_dark = False

    color_key = "text_dark_theme" if is_dark else "text_light_theme"
    return SETTINGS["colors"][color_key]