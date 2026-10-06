# -*- coding: utf-8 -*-
"""Общие UI-хелперы для app.py и блоков."""
import streamlit as st
import traceback


def render_block(title, render_fn, df, cfg, var_labels, val_labels,
                 brand_colors, font_px, freq, is_mobile,
                 enabled=True, disabled_msg=""):
    """Единый вызов блока дашборда с обработкой ошибок."""
    st.header(title)
    if not enabled:
        st.info(disabled_msg)
        return
    try:
        render_fn(df, cfg,
                  var_labels=var_labels,
                  val_labels=val_labels,
                  brand_colors=brand_colors,
                  font_px=font_px,
                  freq=freq,
                  is_mobile=is_mobile)
    except Exception as e:
        st.error(f"Ошибка: {e}")
        with st.expander("Отладка"):
            st.code(traceback.format_exc())
