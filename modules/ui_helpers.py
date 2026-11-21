# -*- coding: utf-8 -*-
"""Общие UI-хелперы для app.py и блоков."""
# modules/ui_helpers.py
# -*- coding: utf-8 -*-
from .config import get_font_size, FONT_FAMILY
import re
import traceback

import streamlit as st


def _prepare_html_for_streamlit(value: str) -> str:
    """
    Убирает переносы строк и отступы из HTML.

    Это важно, потому что многострочный HTML с отступами
    Streamlit может интерпретировать как Markdown-код.
    """

    if not isinstance(value, str):
        return value

    # Убираем переносы строк и пробелы в начале каждой строки
    value = re.sub(r"\s*\n\s*", "", value)

    # Убираем возможные табы
    value = value.replace("\t", "")

    return value.strip()


def render_block(
    title,
    render_fn,
    df,
    cfg,
    var_labels,
    val_labels,
    brand_colors,
    font_px,
    freq,
    is_mobile,
    enabled=True,
    disabled_msg="",
):
    """
    Единый вызов блока с обработкой ошибок.
    """
    title_font = get_font_size("block_title")

    st.markdown(
        f"""
        <style>
        div[data-testid="stHeader"] {{
            font-family: {FONT_FAMILY};
            font-size: {title_font}px;
            font-weight: 700;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<p style="font-family:{FONT_FAMILY};'
        f'font-size:{title_font}px;font-weight:700;'
        f'margin:0 0 1rem 0">{title}</p>',
        unsafe_allow_html=True,
    )

    if not enabled:
        st.info(disabled_msg)
        return

    try:
        result = render_fn(
            df,
            cfg,
            var_labels=var_labels,
            val_labels=val_labels,
            brand_colors=brand_colors,
            font_px=font_px,
            freq=freq,
            is_mobile=is_mobile,
        )

        # Блок может вернуть HTML
        if isinstance(result, str) and result.strip():
            html_result = _prepare_html_for_streamlit(result)

            st.markdown(
                html_result,
                unsafe_allow_html=True,
            )

    except Exception as e:
        st.error(f"Ошибка: {e}")

        with st.expander("Отладка"):
            st.code(traceback.format_exc())