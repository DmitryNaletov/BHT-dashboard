# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import math
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..config import FONT_FAMILY, GRAY, FONT_PX
from ..analytics import (
    format_period, t_test_vs_overall, weighted_mean, weighted_std, fmt_brand_value,
)


def _normalize_key(v):
    if isinstance(v, (int, float)) and float(v).is_integer():
        return str(int(v))
    return str(v)


def _compute_metric_series(df_work, metric_var, brand_var, brand_val, all_periods, weight_var):
    """Возвращает список взвешенных средних по периодам для одного бренда и показателя."""
    mask = df_work[brand_var] == brand_val
    df_brand = df_work[mask]
    series = []
    for period in all_periods:
        df_p = df_brand[df_brand["_period"] == period]
        if len(df_p) > 0:
            w = df_p[weight_var].fillna(1).values
            v = df_p[metric_var].values
            series.append(np.average(v, weights=w) if w.sum() > 0 else np.nan)
        else:
            series.append(np.nan)
    return series


def _compute_significance(df_work, metric_var, brand_var, weight_var, all_periods):
    """Значимость последнего периода: бренд vs остальные (t-тест Уэлча)."""
    sig = {}
    last_period = all_periods[-1]
    df_last = df_work[df_work["_period"] == last_period]
    unique_brands = sorted(df_last[brand_var].unique().tolist())

    for brand_val in unique_brands:
        key = _normalize_key(brand_val)
        mask_b = df_last[brand_var] == brand_val
        df_b = df_last[mask_b]
        df_o = df_last[~mask_b]

        if len(df_b) < 2 or len(df_o) < 2:
            sig[key] = (None, "#999999")
            continue

        w_b = df_b[weight_var].fillna(1).values
        v_b = df_b[metric_var].values
        w_o = df_o[weight_var].fillna(1).values
        v_o = df_o[metric_var].values

        if w_b.sum() == 0 or w_o.sum() == 0:
            sig[key] = (None, "#999999")
            continue

        m1 = np.average(v_b, weights=w_b)
        m2 = np.average(v_o, weights=w_o)
        s1 = weighted_std(v_b, w_b)
        s2 = weighted_std(v_o, w_o)
        n1 = len(df_b)
        n2 = len(df_o)

        is_sig, direction, _ = t_test_vs_overall(m1, s1, n1, m2, s2, n2)
        if is_sig and direction == "up":
            sig[key] = ("up", "green")
        elif is_sig and direction == "down":
            sig[key] = ("down", "red")
        else:
            sig[key] = (None, "#999999")

    return sig


def render_metrics_table(df, cfg, var_labels=None, val_labels=None,
                         brand_colors=None, font_px=16, freq="M", is_mobile=False):

    kpi_var = cfg.get("kpi_var")
    brand_var = cfg.get("brand_var")
    weight_var = cfg.get("weight_var")
    date_var = cfg.get("date_var")
    extra_vars = cfg.get("extra_vars", [])

    if not all([kpi_var, brand_var, weight_var, date_var]):
        st.info("Не настроены ключевые переменные (KPI, бренд, вес, дата).")
        return

    vl = var_labels or {}
    vl_all = val_labels or {}
    brand_vl = vl_all.get(brand_var, {})

    # —— Список показателей ——
    metric_vars = [kpi_var] + [v for v in extra_vars if v in df.columns]
    metric_labels = [vl.get(v, v) for v in metric_vars]

    # —— Подготовка данных ——
    cols_needed = list(set(metric_vars + [brand_var, weight_var, date_var]))
    df_work = df[cols_needed].copy()
    df_work = df_work.dropna(subset=[brand_var, date_var])
    df_work[date_var] = pd.to_datetime(df_work[date_var], errors="coerce")
    df_work = df_work.dropna(subset=[date_var])
    df_work["_period"] = df_work[date_var].dt.to_period(freq)

    unique_brands = sorted(df_work[brand_var].unique().tolist())
    brand_names = [fmt_brand_value(b, brand_vl) for b in unique_brands]
    brand_keys = [_normalize_key(b) for b in unique_brands]
    all_periods = sorted(df_work["_period"].unique().tolist())

    n_metrics = len(metric_vars)
    n_brands = len(unique_brands)

    # —— Расчёт данных ——
    # series_data[metric_idx][brand_idx] = list of values
    series_data = []
    sig_data = []

    for mi, mvar in enumerate(metric_vars):
        df_m = df_work.dropna(subset=[mvar])
        brand_series = []
        for bi, bv in enumerate(unique_brands):
            s = _compute_metric_series(df_m, mvar, brand_var, bv, all_periods, weight_var)
            brand_series.append(s)
        series_data.append(brand_series)

        sig = _compute_significance(df_m, mvar, brand_var, weight_var, all_periods)
        sig_data.append(sig)

    # —— Размеры ячеек ——
    label_col_w = 200 if not is_mobile else 130
    brand_col_w = 160 if not is_mobile else 110
    cell_h = 90 if not is_mobile else 70

    total_w = label_col_w + brand_col_w * n_brands
    total_h = 50 + cell_h * n_metrics  # 50px для заголовка

    # —— Создаём фигуру ——
    # Используем make_subplots: n_metrics строк, n_brands столбцов
    # Все субплоты — scatter (для спарклайнов)
    specs = [[{"type": "scatter"} for _ in range(n_brands)] for _ in range(n_metrics)]

    fig = make_subplots(
        rows=n_metrics,
        cols=n_brands,
        specs=specs,
        horizontal_spacing=0.02,
        vertical_spacing=0.02,
    )

    # —— Добавляем спарклайны ——
    for mi in range(n_metrics):
        for bi in range(n_brands):
            vals = series_data[mi][bi]
            color = (brand_colors or {}).get(brand_keys[bi], "hsl({0}, 70%, 50%)".format(bi * 60 % 360))

            # Фильтруем NaN
            x_vals = list(range(len(vals)))
            y_vals = [v if not np.isnan(v) else None for v in vals]

            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=y_vals,
                    mode="lines",
                    line=dict(color=color, width=2),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=mi + 1,
                col=bi + 1,
            )

            # Убираем оси
            fig.update_xaxes(
                showgrid=False, zeroline=False, showticklabels=False,
                row=mi + 1, col=bi + 1,
            )
            fig.update_yaxes(
                showgrid=False, zeroline=False, showticklabels=False,
                row=mi + 1, col=bi + 1,
            )

    # —— Аннотации через paper-координаты ——
    # Вычисляем позиции вручную
    x_step = 1.0 / n_brands
    y_step = 1.0 / n_metrics

    annotations = []

    # Заголовки столбцов (бренды) — сверху
    for bi, bname in enumerate(brand_names):
        x_pos = bi * x_step + x_step / 2
        annotations.append(dict(
            text="<b>{0}</b>".format(bname),
            x=x_pos, y=1.02,
            xref="paper", yref="paper",
            xanchor="center", yanchor="bottom",
            showarrow=False,
            font=dict(size=font_px, family=FONT_FAMILY, color="#333333"),
        ))

    # Заголовки строк (показатели) — слева, через paper-координаты
    # Используем отрицательный x для левой колонки
    for mi, mlabel in enumerate(metric_labels):
        y_pos = 1.0 - (mi + 0.5) * y_step
        annotations.append(dict(
            text=mlabel,
            x=-0.001, y=y_pos,
            xref="paper", yref="paper",
            xanchor="right", yanchor="middle",
            showarrow=False,
            font=dict(size=font_px, family=FONT_FAMILY, color="#333333"),
        ))

    # Значения последнего периода + значимость
    val_font_size = max(int(font_px * 0.85), 10)

    for mi in range(n_metrics):
        for bi in range(n_brands):
            vals = series_data[mi][bi]
            if not vals or all(np.isnan(v) for v in vals):
                continue

            last_val = vals[-1]
            if np.isnan(last_val):
                continue

            sig_dir, sig_color = sig_data[mi].get(brand_keys[bi], (None, "#999999"))

            if sig_dir == "up":
                arrow = " \u25b2"
            elif sig_dir == "down":
                arrow = " \u25bc"
            else:
                arrow = ""

            text = "{0:.2f}{1}".format(last_val, arrow)
            color = sig_color if sig_dir else "#333333"

            x_pos = bi * x_step + x_step / 2
            y_pos = 1.0 - (mi + 1) * y_step + 0.02

            annotations.append(dict(
                text=text,
                x=x_pos, y=y_pos,
                xref="paper", yref="paper",
                xanchor="center", yanchor="bottom",
                showarrow=False,
                font=dict(size=val_font_size, family=FONT_FAMILY, color=color),
            ))

    # —— Линии-разделители через shapes (paper-координаты) ——
    shapes = []

    # Горизонтальные линии между строками
    for mi in range(n_metrics + 1):
        y = 1.0 - mi * y_step
        shapes.append(dict(
            type="line",
            x0=0, x1=1.0,
            y0=y, y1=y,
            xref="paper", yref="paper",
            line=dict(color="#e0e0e0", width=1),
        ))

    # Вертикальные линии между столбцами
    for bi in range(n_brands + 1):
        x = bi * x_step
        shapes.append(dict(
            type="line",
            x0=x, x1=x,
            y0=0, y1=1.0,
            xref="paper", yref="paper",
            line=dict(color="#e0e0e0", width=1),
        ))

    fig.update_layout(
        annotations=annotations,
        shapes=shapes,
        margin=dict(l=label_col_w, r=20, t=60, b=20),
        height=total_h,
        width=total_w,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        hovermode=False,
    )

    st.plotly_chart(fig, use_container_width=True)
