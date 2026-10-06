import pandas as pd
import streamlit as st
from collections import Counter
import re
import math
import plotly.graph_objects as go

from ..analytics import format_period, fmt_brand_value
from ..config import FONT_FAMILY, GRAY

def _get_comment_vars(df, cfg):
    """Return only string (text) variables from comment_vars."""
    comment_vars = cfg.get("comment_vars", [])
    text_vars = []
    for var in comment_vars:
        if var in df.columns and not pd.api.types.is_numeric_dtype(df[var]):
            text_vars.append(var)
    return text_vars

def render_wordcloud_block(df, cfg, var_labels=None, val_labels=None,
                           brand_colors=None, font_px=16, freq="M", is_mobile=False):

    text_vars = _get_comment_vars(df, cfg)
    if not text_vars:
        st.info("Среди выбранных переменных нет текстовых (открытых вопросов) для облака слов.")
        return

    vl = var_labels or {}
    var_options = [v + " \u2014 " + vl.get(v, v) if vl.get(v) else v for v in text_vars]
    display_to_var = dict(zip(var_options, text_vars))

    sel_var_display = st.selectbox("Открытый вопрос", var_options, key="wc_var_sel")
    sel_var = display_to_var[sel_var_display]

    brand_var = cfg.get("brand_var")
    if not brand_var or brand_var not in df.columns:
        st.warning("Бренд не настроен.")
        return

    brand_vl = (val_labels or {}).get(brand_var, {})
    unique_brands = sorted(df[brand_var].dropna().unique().tolist())

    brand_display = [fmt_brand_value(b, brand_vl) for b in unique_brands]
    brand_map = dict(zip(brand_display, unique_brands))
    sel_brand_display = st.selectbox("Бренд", brand_display, key="wc_brand_sel")
    sel_brand = brand_map[sel_brand_display]

    # —— Фильтр по периоду (множественный, согласован с freq) ——
    date_var = cfg.get("date_var")
    period_labels = []
    period_values = []
    if date_var and date_var in df.columns:
        dt_series = pd.to_datetime(df[date_var], errors="coerce")
        valid = dt_series.dropna()
        if len(valid) > 0:
            periods = valid.dt.to_period(freq)
            unique_periods = sorted(periods.unique().tolist())
            period_labels = [format_period(p, freq) for p in unique_periods]
            period_values = unique_periods
            period_label_to_val = dict(zip(period_labels, period_values))

            # Динамический ключ виджета — при смене freq это новый виджет
            period_widget_key = f"wc_period_sel_{freq}"
            default_periods = [period_labels[-1]] if period_labels else []
            sel_period_labels = st.multiselect(
                "Период",
                period_labels,
                default=default_periods,
                key=period_widget_key,
            )
            sel_periods = [period_label_to_val[l] for l in sel_period_labels] if sel_period_labels else period_values

            # Фильтруем df по выбранным периодам
            mask = periods.isin(sel_periods) & periods.notna()
            df = df[mask.reindex(df.index, fill_value=False)].copy()

    sel_brand_key = str(sel_brand)
    if isinstance(sel_brand, (int, float)) and float(sel_brand).is_integer():
        sel_brand_key = str(int(sel_brand))

    df_brand = df[df[brand_var] == sel_brand].copy()
    text_series = df_brand[sel_var].dropna().astype(str)
    texts_all = text_series.tolist()
    text_indices = text_series.index.tolist()

    if not texts_all:
        st.info("Нет текстовых ответов для выбранного бренда и периода.")
        return

    # —— Частоты слов ——
    word_freq = Counter()
    for text in texts_all:
        words = re.findall(r"[\u0430-\u044f\u0451\u0410-\u042f\u0401a-zA-Z]+", text.lower())
        word_freq.update(words)

    if not word_freq:
        st.info("Не удалось извлечь слова из ответов.")
        return

    top_words = word_freq.most_common(50)

    # —— Z-тест для значимости слов ——
    # Доля слова у выбранного бренда vs у остальных брендов
    n_sel = len(texts_all)
    texts_other = df[df[brand_var] != sel_brand][sel_var].dropna().astype(str).tolist()
    n_other = len(texts_other) if texts_other else 0

    word_freq_other = Counter()
    for text in texts_other:
        words = re.findall(r"[\u0430-\u044f\u0451\u0410-\u042f\u0401a-zA-Z]+", text.lower())
        word_freq_other.update(words)

    # Доли по брендам для определения лидирующего бренда
    brand_word_shares = {}
    for bv in unique_brands:
        bv_texts = df[df[brand_var] == bv][sel_var].dropna().astype(str).tolist()
        bv_freq = Counter()
        for t in bv_texts:
            bv_freq.update(re.findall(r"[\u0430-\u044f\u0451\u0410-\u042f\u0401a-zA-Z]+", t.lower()))
        n_bv = len(bv_texts) if bv_texts else 0
        brand_word_shares[str(bv)] = (bv_freq, n_bv)

    # Цвета брендов
    bc = brand_colors or {}

    def get_brand_color(bv):
        key = str(int(bv)) if isinstance(bv, (int, float)) and float(bv).is_integer() else str(bv)
        return bc.get(key, "hsl(210, 70%, 50%)")

    # —— Раскладка облака ——
    max_count = top_words[0][1] if top_words else 1
    min_count = top_words[-1][1] if top_words else 1

    placed = []
    cloud_x = []
    cloud_y = []
    cloud_text = []
    cloud_size = []
    cloud_color = []
    cloud_hover = []

    cx, cy = 0.0, 0.0

    for word, count in top_words:
        if max_count == min_count:
            size = 40
        else:
            ratio = (count - min_count) / max(1, max_count - min_count)
            size = int(14 + ratio * 66)
        est_w = len(word) * size * 0.6
        est_h = size

        # Z-тест
        p_sel = count / n_sel if n_sel > 0 else 0
        count_other = word_freq_other.get(word, 0)
        p_other = count_other / n_other if n_other > 0 else 0
        p_pool = (count + count_other) / (n_sel + n_other) if (n_sel + n_other) > 0 else 0
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / max(n_sel, 1) + 1 / max(n_other, 1))) if p_pool > 0 else 0
        z = (p_sel - p_other) / se if se > 0 else 0

        # Цвет
        if z >= 1.96:
            color = get_brand_color(sel_brand)
        elif z <= -1.96:
            # Найти лидирующий бренд
            leading_brand = None
            leading_share = -1
            for bv in unique_brands:
                bv_key = str(bv)
                bv_freq, n_bv = brand_word_shares.get(bv_key, (Counter(), 0))
                share = bv_freq.get(word, 0) / n_bv if n_bv > 0 else 0
                if share > leading_share:
                    leading_share = share
                    leading_brand = bv
            color = get_brand_color(leading_brand) if leading_brand is not None else GRAY
        else:
            color = GRAY

        placed_ok = False
        for radius in range(0, 400, 5):
            for angle in range(0, 360, 15):
                rad = math.radians(angle)
                x = cx + radius * math.cos(rad)
                y = cy + radius * math.sin(rad)

                overlap = False
                for px, py, pw, ph in placed:
                    if not (x + est_w / 2 < px - pw / 2 or
                            x - est_w / 2 > px + pw / 2 or
                            y + est_h / 2 < py - ph / 2 or
                            y - est_h / 2 > py + ph / 2):
                        overlap = True
                        break

                if not overlap:
                    placed.append((x, y, est_w, est_h))
                    cloud_x.append(x)
                    cloud_y.append(y)
                    cloud_text.append(word)
                    cloud_size.append(size)
                    cloud_color.append(color)
                    cloud_hover.append(word + " (" + str(count) + ")")
                    placed_ok = True
                    break
            if placed_ok:
                break

    # —— Сброс выбора слова при смене контекста ——
    ctx_key = f"{sel_var}|{sel_brand_display}|{freq}"
    if st.session_state.get("wc_ctx_key") != ctx_key:
        st.session_state["wc_ctx_key"] = ctx_key
        st.session_state.pop("wc_sel_word", None)
        st.session_state["wc_chart_key"] = st.session_state.get("wc_chart_key", 0) + 1

    chart_key_val = st.session_state.get("wc_chart_key", 0)

    fig_cloud = go.Figure()
    fig_cloud.add_trace(go.Scatter(
        x=cloud_x,
        y=cloud_y,
        mode="text+markers",
        text=cloud_text,
        textfont=dict(size=cloud_size, color=cloud_color, family=FONT_FAMILY),
        marker=dict(opacity=0, size=20),
        hoverinfo="text",
        hovertext=cloud_hover,
        showlegend=False,
    ))
    fig_cloud.update_layout(
        xaxis=dict(visible=False, range=[-420, 420]),
        yaxis=dict(visible=False, range=[-220, 220]),
        margin=dict(l=0, r=0, t=0, b=0),
        height=400,
        font=dict(family=FONT_FAMILY, size=font_px, color=GRAY),
    )

    event = st.plotly_chart(fig_cloud, width="stretch",
                            on_select="rerun", key=f"wc_cloud_{chart_key_val}")

    # —— Обработка клика ——
    sel_word = st.session_state.get("wc_sel_word")

    if event and event.selection and len(event.selection.point_indices) > 0:
        clicked_idx = event.selection.point_indices[0]
        clicked_word = cloud_text[clicked_idx] if clicked_idx < len(cloud_text) else None
        if clicked_word:
            if sel_word == clicked_word:
                # Toggle — повторный клик по тому же слову сбрасывает
                st.session_state.pop("wc_sel_word", None)
                st.session_state["wc_chart_key"] = chart_key_val + 1
                st.rerun()
            else:
                st.session_state["wc_sel_word"] = clicked_word
                sel_word = clicked_word

    # —— Фрагмент: таблица цитат (перерисовывается только таблица) ——
    @st.fragment
    def _render_citation_table():
        sel_w = st.session_state.get("wc_sel_word")

        records = []
        for row_idx, text in zip(text_indices, texts_all):
            records.append({"\u0421\u0442\u0440\u043e\u043a\u0430": row_idx, "\u0422\u0435\u043a\u0441\u0442 \u043e\u0442\u0432\u0435\u0442\u0430": text})

        if sel_w:
            records = [r for r in records if sel_w.lower() in r["\u0422\u0435\u043a\u0441\u0442 \u043e\u0442\u0432\u0435\u0442\u0430"].lower()]

        col_btn, col_info = st.columns([1, 5])
        with col_btn:
            if sel_w:
                if st.button("\u2716 Сбросить", key="wc_reset_btn"):
                    st.session_state.pop("wc_sel_word", None)
                    st.session_state["wc_chart_key"] = st.session_state.get("wc_chart_key", 0) + 1
                    st.rerun()
        with col_info:
            if sel_w:
                st.caption(f"\u0424\u0438\u043b\u044c\u0442\u0440: \u00ab{sel_w}\u00bb \u2014 {len(records)} \u0438\u0437 {len(texts_all)}")
            else:
                st.caption(f"\u0412\u0441\u0435\u0433\u043e \u0446\u0438\u0442\u0430\u0442: {len(texts_all)}")

        if records:
            import html as _html
            rows_html = ""
            for r in records:
                row_num = _html.escape(str(r["\u0421\u0442\u0440\u043e\u043a\u0430"]))
                row_text = _html.escape(str(r["\u0422\u0435\u043a\u0441\u0442 \u043e\u0442\u0432\u0435\u0442\u0430"]))
                rows_html += f'<tr><td class="col-num">{row_num}</td><td class="col-text">{row_text}</td></tr>\n'
            table_html = f"""<style>
.wc-table {{ width: 100%; border-collapse: collapse; font-family: Inter, -apple-system, sans-serif; font-size: 14px; }}
.wc-table th {{ position: sticky; top: 0; background: #f0f2f6; padding: 8px 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #e0e0e0; }}
.wc-table td {{ padding: 8px 12px; border-bottom: 1px solid #eaeaea; vertical-align: top; }}
.wc-table tbody tr:nth-child(even) {{ background: #fafafa; }}
.wc-table tbody tr:hover {{ background: #f5f5f5; }}
.wc-table .col-num {{ width: 60px; min-width: 60px; max-width: 60px; text-align: center; white-space: nowrap; }}
.wc-table .col-text {{ width: auto; }}
.wc-table-wrap {{ max-height: 400px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 4px; }}
</style>
<div class="wc-table-wrap"><table class="wc-table"><thead><tr><th>\u0421\u0442\u0440\u043e\u043a\u0430</th><th>\u0422\u0435\u043a\u0441\u0442 \u043e\u0442\u0432\u0435\u0442\u0430</th></tr></thead><tbody>{rows_html}</tbody></table></div>"""
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.info("\u041d\u0435\u0442 \u0446\u0438\u0442\u0430\u0442, \u0441\u043e\u0434\u0435\u0440\u0436\u0430\u0449\u0438\u0445 \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u0435 \u0441\u043b\u043e\u0432\u043e.")

    _render_citation_table()
