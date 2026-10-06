import pandas as pd
import plotly.graph_objects as go
import numpy as np
import math
import streamlit as st

from ..config import FONT_FAMILY, GRAY, FONT_PX
from ..analytics import (
    format_period, t_test_vs_overall, weighted_mean, weighted_std, fmt_brand_value,
)

def _build_chart(df, cfg, freq, var_labels, val_labels, brand_colors, font_px, is_mobile):
    kpi_var = cfg["kpi_var"]
    brand_var = cfg["brand_var"]
    weight_var = cfg["weight_var"]
    date_var = cfg["date_var"]

    vl = val_labels or {}

    df_work = df[[kpi_var, brand_var, weight_var, date_var]].copy()
    df_work = df_work.dropna(subset=[kpi_var, brand_var, date_var])
    df_work[date_var] = pd.to_datetime(df_work[date_var], errors="coerce")
    df_work = df_work.dropna(subset=[date_var])
    df_work["_period"] = df_work[date_var].dt.to_period(freq)

    unique_brands = sorted(df_work[brand_var].unique().tolist())
    brand_val_labels = vl.get(brand_var, {})
    brand_names = [fmt_brand_value(b, brand_val_labels) for b in unique_brands]

    all_periods = sorted(df_work["_period"].unique().tolist())
    period_labels = [format_period(p, freq) for p in all_periods]
    vertical_text = len(all_periods) > 6
    n_brands = len(unique_brands)

    # Средние по брендам для каждого периода
    results = {}
    for brand_val in unique_brands:
        brand_key = str(int(brand_val)) if isinstance(brand_val, (int, float)) and float(brand_val).is_integer() else str(brand_val)
        mask = df_work[brand_var] == brand_val
        df_brand = df_work[mask]
        kpi_series = []
        for period in all_periods:
            df_p = df_brand[df_brand["_period"] == period]
            if len(df_p) > 0:
                w = df_p[weight_var].fillna(1).values
                v = df_p[kpi_var].values
                kpi_series.append(np.average(v, weights=w) if w.sum() > 0 else np.nan)
            else:
                kpi_series.append(np.nan)
        results[brand_key] = kpi_series

    # Значимость последнего периода: бренд vs остальные (t-тест Уэлча)
    sig_colors = {}
    sig_directions = {}
    last_period = all_periods[-1]
    df_last = df_work[df_work["_period"] == last_period]

    for brand_val in unique_brands:
        brand_key = str(int(brand_val)) if isinstance(brand_val, (int, float)) and float(brand_val).is_integer() else str(brand_val)
        mask_b = df_last[brand_var] == brand_val
        df_b = df_last[mask_b]
        df_o = df_last[~mask_b]

        if len(df_b) < 2 or len(df_o) < 2:
            sig_colors[brand_key] = "#999999"
            sig_directions[brand_key] = None
            continue

        w_b = df_b[weight_var].fillna(1).values
        v_b = df_b[kpi_var].values
        w_o = df_o[weight_var].fillna(1).values
        v_o = df_o[kpi_var].values

        if w_b.sum() == 0 or w_o.sum() == 0:
            sig_colors[brand_key] = "#999999"
            sig_directions[brand_key] = None
            continue

        m1 = np.average(v_b, weights=w_b)
        m2 = np.average(v_o, weights=w_o)
        s1 = weighted_std(v_b, w_b)
        s2 = weighted_std(v_o, w_o)
        n1 = len(df_b)
        n2 = len(df_o)

        is_sig, direction, _ = t_test_vs_overall(m1, s1, n1, m2, s2, n2)
        if is_sig and direction == "up":
            sig_colors[brand_key] = "green"
            sig_directions[brand_key] = "up"
        elif is_sig and direction == "down":
            sig_colors[brand_key] = "red"
            sig_directions[brand_key] = "down"
        else:
            sig_colors[brand_key] = "#999999"
            sig_directions[brand_key] = None

    fig = go.Figure()

    # ВАЖНО: отключаем автомасштабирование текста. 
    # uniformtext_minsize=12 — минимальный размер, который Plotly не будет уменьшать.
    # uniformtext_mode='hide' — если текст не влезает, он скроется (лучше, чем становиться микроскопическим).
    # Если хотите, чтобы текст всегда был виден даже ценой наложения, используйте mode='show'
    fig.update_layout(
        uniformtext_minsize=12, 
        uniformtext_mode='show',  # Или 'hide', если наезжание совсем недопустимо
    )

    for i, brand_val in enumerate(unique_brands):
        brand_key = str(int(brand_val)) if isinstance(brand_val, (int, float)) and float(brand_val).is_integer() else str(brand_val)
        brand_name = brand_names[i]
        color = (brand_colors or {}).get(brand_key, "hsl(" + str(i * 60 % 360) + ", 70%, 50%)")

        y_vals = results[brand_key]
        x_labels = period_labels

        # Метки — всегда средние (не проценты), всегда снаружи
        text_vals = []
        for j, v in enumerate(y_vals):
            if np.isnan(v):
                text_vals.append("")
                continue
            is_last = (j == len(y_vals) - 1)
            if is_last and sig_directions.get(brand_key) == "up":
                text_vals.append("{:.2f}\n\u25b2".format(v))
            elif is_last and sig_directions.get(brand_key) == "down":
                text_vals.append("{:.2f}\n\u25bc".format(v))
            else:
                text_vals.append("{:.2f}".format(v))

        safe_font_size = max(int(font_px), 12)

        fig.add_trace(go.Bar(
            x=x_labels,
            y=y_vals,
            name=brand_name,
            marker_color=color,
            text=text_vals,
            textposition="outside",
            textangle=270 if vertical_text else 0,
            # Единый размер для всех меток — это работает в Plotly
            textfont=dict(size=safe_font_size, color=GRAY, family=FONT_FAMILY),
            hovertemplate=brand_name + "<br>%{x}: %{y:.2f}<extra></extra>",
        ))

    # —— Динамический расчёт высоты подписей оси X и легенды ——
    if vertical_text:
        max_label_len = max(len(p) for p in period_labels)
        xaxis_space = max_label_len * font_px * 0.65 + 15
    else:
        xaxis_space = font_px + 15

    items_per_row = 3 if is_mobile else 5
    n_legend_rows = max(1, math.ceil(n_brands / items_per_row))
    legend_h = n_legend_rows * (font_px + 8)

    t_margin = 20
    b_margin = int(xaxis_space + legend_h + 25)

    total_height = max(600, n_brands * 35 + 200)
    if vertical_text:
        total_height = max(total_height, 600 + xaxis_space * 0.4)

    plot_area_h = total_height - t_margin - b_margin
    if plot_area_h > 0:
        legend_y = -(xaxis_space + 8) / plot_area_h
    else:
        legend_y = -0.20

    fig.update_layout(
        barmode="group",
        font=dict(family=FONT_FAMILY, size=font_px, color=GRAY),
        title=None,
        xaxis=dict(
            tickangle=270 if vertical_text else 0,
            tickfont=dict(size=font_px, family=FONT_FAMILY),
        ),
        yaxis=dict(
            tickfont=dict(size=font_px, family=FONT_FAMILY),
            title=None,
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=legend_y,
            xanchor="center",
            x=0.5,
            font=dict(size=font_px, family=FONT_FAMILY),
        ),
        margin=dict(l=0, r=0, t=t_margin, b=b_margin),
        bargap=0.3,
        bargroupgap=0.15,
        height=total_height,
        showlegend=True,
    )

    return fig


def _build_table(df, cfg, freq, var_labels, val_labels, brand_colors, font_px):
    kpi_var = cfg["kpi_var"]
    brand_var = cfg["brand_var"]
    weight_var = cfg["weight_var"]
    date_var = cfg["date_var"]

    vl = val_labels or {}

    df_work = df[[kpi_var, brand_var, weight_var, date_var]].copy()
    df_work = df_work.dropna(subset=[kpi_var, brand_var, date_var])
    df_work[date_var] = pd.to_datetime(df_work[date_var], errors="coerce")
    df_work = df_work.dropna(subset=[date_var])
    df_work["_period"] = df_work[date_var].dt.to_period(freq)

    unique_brands = sorted(df_work[brand_var].unique().tolist())
    brand_val_labels = vl.get(brand_var, {})
    brand_names = [fmt_brand_value(b, brand_val_labels) for b in unique_brands]

    all_periods = sorted(df_work["_period"].unique().tolist())
    period_labels = [format_period(p, freq) for p in all_periods]

    rows = []
    for brand_val in unique_brands:
        brand_key = str(int(brand_val)) if isinstance(brand_val, (int, float)) and float(brand_val).is_integer() else str(brand_val)
        mask = df_work[brand_var] == brand_val
        df_brand = df_work[mask]
        row = {"Бренд": fmt_brand_value(brand_val, brand_val_labels)}
        for period, plabel in zip(all_periods, period_labels):
            df_p = df_brand[df_brand["_period"] == period]
            if len(df_p) > 0:
                w = df_p[weight_var].fillna(1).values
                v = df_p[kpi_var].values
                row[plabel] = "{:.2f}".format(np.average(v, weights=w)) if w.sum() > 0 else ""
            else:
                row[plabel] = ""
        rows.append(row)

    table_df = pd.DataFrame(rows)
    st.dataframe(table_df, use_container_width=True, hide_index=True)


def render_kpi_dynamics(df, cfg, freq="M",
                        var_labels=None, val_labels=None,
                        brand_colors=None, font_px=16, is_mobile=False):
    view = st.radio("Просмотр", ["График", "Таблица"], horizontal=True, key="b1_view")
    if view == "График":
        fig = _build_chart(df, cfg, freq, var_labels, val_labels,
                           brand_colors, font_px, is_mobile)
        st.plotly_chart(fig, use_container_width=True)
    else:
        _build_table(df, cfg, freq, var_labels, val_labels, brand_colors, font_px)
