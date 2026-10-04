# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import math
import streamlit as st
import plotly.graph_objects as go
from .axis_utils import prepare_axes, to_px
from .label_placement import align_labels

def _format_period(period, freq):
    if freq == "Y":
        return str(period.year)
    elif freq == "Q":
        return f"Q{period.quarter} {str(period.year)[2:]}"
    elif freq == "M":
        months_ru = ["\u042f\u043d\u0432", "\u0424\u0435\u0432", "\u041c\u0430\u0440",
                     "\u0410\u043f\u0440", "\u041c\u0430\u0439", "\u0418\u044e\u043d",
                     "\u0418\u044e\u043b", "\u0410\u0432\u0433", "\u0421\u0435\u043d",
                     "\u041e\u043a\u0442", "\u041d\u043e\u044f", "\u0414\u0435\u043a"]
        return f"{months_ru[period.month - 1]} {str(period.year)[2:]}"
    elif freq == "W":
        return f"{period.year}-W{period.week:02d}"
    else:
        return str(period)



def render_competitive_map(df, cfg, var_labels=None, val_labels=None,
                           brand_colors=None, font_px=16, freq="M", is_mobile=False):
    font_family = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    GRAY = "#999999"

    brand_var = cfg.get("brand_var")
    kpi_var = cfg.get("kpi_var")
    weight_var = cfg.get("weight_var")
    extra_vars = cfg.get("extra_vars", [])

    if not brand_var or brand_var not in df.columns:
        st.warning("\u0411\u0440\u0435\u043d\u0434 \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d.")
        return
    if not kpi_var or kpi_var not in df.columns:
        st.warning("KPI \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d.")
        return
    if not extra_vars:
        st.info("\u041d\u0435\u0442 \u0434\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u0435\u0439 (extra_vars) \u0434\u043b\u044f \u043a\u043e\u043d\u043a\u0443\u0440\u0435\u043d\u0442\u043d\u043e\u0439 \u043a\u0430\u0440\u0442\u044b.")
        return

    vl = var_labels or {}
    brand_vl = (val_labels or {}).get(brand_var, {})
    unique_brands = sorted(df[brand_var].dropna().unique().tolist())

    def fmt_brand(v):
        key = str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v)
        return brand_vl.get(key, str(v))

    brand_display = [fmt_brand(b) for b in unique_brands]
    brand_map = dict(zip(brand_display, unique_brands))
    sel_brand_display = st.selectbox("\u0411\u0440\u0435\u043d\u0434", brand_display, key="cm_brand_sel")
    sel_brand = brand_map[sel_brand_display]

    # —— Фильтр по периоду ——
    date_var = cfg.get("date_var")
    if date_var and date_var in df.columns:
        dt_series = pd.to_datetime(df[date_var], errors="coerce")
        valid = dt_series.dropna()
        if len(valid) > 0:
            periods = valid.dt.to_period(freq)
            unique_periods = sorted(periods.unique().tolist())
            period_labels = [_format_period(p, freq) for p in unique_periods]
            period_values = unique_periods
            period_label_to_val = dict(zip(period_labels, period_values))

            period_widget_key = f"cm_period_sel_{freq}"
            default_periods = [period_labels[-1]] if period_labels else []
            sel_period_labels = st.multiselect(
                "\u041f\u0435\u0440\u0438\u043e\u0434",
                period_labels,
                default=default_periods,
                key=period_widget_key,
            )
            sel_periods = [period_label_to_val[l] for l in sel_period_labels] if sel_period_labels else period_values
            mask = periods.isin(sel_periods) & periods.notna()
            df = df[mask.reindex(df.index, fill_value=False)].copy()

    # —— Цвета брендов ——
    bc = brand_colors or {}

    def get_brand_color(bv):
        key = str(int(bv)) if isinstance(bv, (int, float)) and float(bv).is_integer() else str(bv)
        return bc.get(key, "hsl(210, 70%, 50%)")

    sel_brand_color = get_brand_color(sel_brand)

    # —— Вычисления ——
    w_all = df[weight_var] if weight_var and weight_var in df.columns else None

    def weighted_corr(x, y, w):
        mask = x.notna() & y.notna()
        if w is not None:
            mask = mask & w.notna()
        x_v = x[mask].values
        y_v = y[mask].values
        w_v = w[mask].values if w is not None else np.ones(len(x_v))
        if len(x_v) < 3:
            return np.nan
        w_v = w_v / w_v.sum()
        x_m = np.average(x_v, weights=w_v)
        y_m = np.average(y_v, weights=w_v)
        cov = np.average((x_v - x_m) * (y_v - y_m), weights=w_v)
        x_std = np.sqrt(np.average((x_v - x_m) ** 2, weights=w_v))
        y_std = np.sqrt(np.average((y_v - y_m) ** 2, weights=w_v))
        if x_std == 0 or y_std == 0:
            return np.nan
        return float(cov / (x_std * y_std))

    def weighted_mean(x, w):
        mask = x.notna()
        if w is not None:
            mask = mask & w.notna()
        x_v = x[mask].values
        w_v = w[mask].values if w is not None else np.ones(len(x_v))
        if len(x_v) == 0:
            return np.nan
        return float(np.average(x_v, weights=w_v))

    kpi = df[kpi_var]
    df_sel = df[df[brand_var] == sel_brand]

    points_data = []

    for var in extra_vars:
        if var not in df.columns:
            continue

        corr = weighted_corr(df[var], kpi, w_all)
        if np.isnan(corr):
            continue

        mean_sel = weighted_mean(df_sel[var], w_all)

        best_mean = -np.inf
        best_brand = None
        for bv in unique_brands:
            if bv == sel_brand:
                continue
            df_bv = df[df[brand_var] == bv]
            m = weighted_mean(df_bv[var], w_all)
            if not np.isnan(m) and m > best_mean:
                best_mean = m
                best_brand = bv

        if best_brand is None or np.isnan(mean_sel) or np.isnan(best_mean):
            continue

        diff = float(mean_sel) - float(best_mean)
        label = vl.get(var, var)

        points_data.append({
            "var": var,
            "label": label,
            "corr": float(corr),
            "diff": diff,
            "mean_sel": float(mean_sel),
            "mean_leader": float(best_mean),
            "leader_brand": best_brand,
            "leader_color": get_brand_color(best_brand),
        })

    if not points_data:
        st.info("\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u043f\u043e\u0441\u0442\u0440\u043e\u0435\u043d\u0438\u044f \u043a\u043e\u043d\u043a\u0443\u0440\u0435\u043d\u0442\u043d\u043e\u0439 \u043a\u0430\u0440\u0442\u044b.")
        return

    corrs = [p["corr"] for p in points_data]
    diffs = [p["diff"] for p in points_data]

    corr_mean = float(np.nanmean(corrs))



    # —— Размещение меток ——
    label_list = [p["label"] for p in points_data]
    
    # Получаем диапазоны осей
    x_range, y_range = prepare_axes(corrs, diffs)
    x_min, x_max = x_range  # Распаковываем значения
    y_min, y_max = y_range  # Распаковываем значения

    # Рассчитываем dtick на основе диапазона X
    x_range_span = x_max - x_min
    if x_range_span <= 0.3:
        dtick = 0.05
    elif x_range_span <= 0.6:
        dtick = 0.1
    elif x_range_span <= 1.2:
        dtick = 0.2
    else:
        dtick = 0.5
        
    # Затем вычисляем смещения меток
    label_offsets = align_labels(
        corrs, diffs, label_list,
        x_range, y_range,
        plot_w=600, plot_h=600, point_size=20, label_gap=10  # Добавить параметры размера графика
    )

    # —— Построение графика ——
    fig = go.Figure()

    # Квадранты
    fig.add_shape(type="rect", xref="x", yref="y",
                  x0=corr_mean, y0=0, x1=x_max, y1=y_max,
                  fillcolor="rgba(76, 175, 80, 0.06)", line_width=0, layer="below")
    fig.add_shape(type="rect", xref="x", yref="y",
                  x0=corr_mean, y0=y_min, x1=x_max, y1=0,
                  fillcolor="rgba(244, 67, 54, 0.06)", line_width=0, layer="below")
    fig.add_shape(type="rect", xref="x", yref="y",
                  x0=x_min, y0=0, x1=corr_mean, y1=y_max,
                  fillcolor="rgba(33, 150, 243, 0.06)", line_width=0, layer="below")
    fig.add_shape(type="rect", xref="x", yref="y",
                  x0=x_min, y0=y_min, x1=corr_mean, y1=0,
                  fillcolor="rgba(158, 158, 158, 0.06)", line_width=0, layer="below")

    # Оси
    fig.add_hline(y=0, line_color=GRAY, line_width=1.5, line_dash="solid")
    fig.add_vline(x=corr_mean, line_color=GRAY, line_width=1.5, line_dash="dash")

    # Точки
    x_above = [p["corr"] for p in points_data if p["diff"] > 0]
    y_above = [p["diff"] for p in points_data if p["diff"] > 0]
    colors_above = [sel_brand_color] * len(x_above)

    x_below = [p["corr"] for p in points_data if p["diff"] <= 0]
    y_below = [p["diff"] for p in points_data if p["diff"] <= 0]
    colors_below = [p["leader_color"] for p in points_data if p["diff"] <= 0]

    hover_above = [f"<b>{p['label']}</b><br>\u041a\u043e\u0440\u0440\u0435\u043b\u044f\u0446\u0438\u044f: {p['corr']:.3f}<br>\u0420\u0430\u0437\u043d\u0438\u0446\u0430: {p['diff']:+.3f}<br>\u0411\u0440\u0435\u043d\u0434: {fmt_brand(sel_brand)}"
                   for p in points_data if p["diff"] > 0]
    hover_below = [f"<b>{p['label']}</b><br>\u041a\u043e\u0440\u0440\u0435\u043b\u044f\u0446\u0438\u044f: {p['corr']:.3f}<br>\u0420\u0430\u0437\u043d\u0438\u0446\u0430: {p['diff']:+.3f}<br>\u041b\u0438\u0434\u0435\u0440: {fmt_brand(p['leader_brand'])}"
                   for p in points_data if p["diff"] <= 0]

    fig.add_trace(go.Scatter(
        x=x_above, y=y_above,
        mode="markers",
        marker=dict(size=12, color=colors_above, line=dict(width=1, color="white")),
        hoverinfo="text", hovertext=hover_above,
        showlegend=False,
    ))

    fig.add_trace(go.Scatter(
        x=x_below, y=y_below,
        mode="markers",
        marker=dict(size=12, color=colors_below, line=dict(width=1, color="white")),
        hoverinfo="text", hovertext=hover_below,
        showlegend=False,
    ))

    # Метки с выносками
    for i, p in enumerate(points_data):
        dx, dy = label_offsets[i]
        fig.add_annotation(
            x=p["corr"], y=p["diff"],
            ax=dx, ay=dy,
            axref="pixel", ayref="pixel",
            text=p["label"],
            showarrow=True,
            arrowhead=0,
            arrowwidth=0.5,
            arrowcolor="rgba(150,150,150,0.6)",
            font=dict(size=11, family=font_family, color="#333333"),
            bgcolor="rgba(255,255,255,0)",
            borderpad=0,
            standoff=2,
        )

    # Подписи квадрантов — прижаты к углам
    fig.add_annotation(
        x=x_max - (x_max - corr_mean) * 0.03,
        y=y_max - (y_max - 0) * 0.05,
        text="\u0421\u0438\u043b\u044c\u043d\u044b\u0435 \u0441\u0442\u043e\u0440\u043e\u043d\u044b",
        showarrow=False,
        font=dict(size=12, color="rgba(76,175,80,0.8)", family=font_family),
        xanchor="right",
        yanchor="top",
    )
    fig.add_annotation(
        x=x_max - (x_max - corr_mean) * 0.03,
        y=y_min + (0 - y_min) * 0.05,
        text="\u0423\u0433\u0440\u043e\u0437\u044b",
        showarrow=False,
        font=dict(size=12, color="rgba(244,67,54,0.8)", family=font_family),
        xanchor="right",
        yanchor="bottom",
    )
    fig.add_annotation(
        x=x_min + (corr_mean - x_min) * 0.03,
        y=y_max - (y_max - 0) * 0.05,
        text="\u041d\u0438\u0448\u0435\u0432\u044b\u0435 \u043f\u0440\u0435\u0438\u043c\u0443\u0449\u0435\u0441\u0442\u0432\u0430",
        showarrow=False,
        font=dict(size=12, color="rgba(33,150,243,0.8)", family=font_family),
        xanchor="left",
        yanchor="top",
    )
    fig.add_annotation(
        x=x_min + (corr_mean - x_min) * 0.03,
        y=y_min + (0 - y_min) * 0.05,
        text="\u041d\u0438\u0437\u043a\u0438\u0439 \u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442",
        showarrow=False,
        font=dict(size=12, color="rgba(158,158,158,0.8)", family=font_family),
        xanchor="left",
        yanchor="bottom",
    )

    # Далее используем dtick в настройках оси
    fig.update_layout(
        xaxis=dict(
        title="Корреляция с KPI",
        range=[x_min, x_max],
        tickformat=".2f",
        dtick=dtick,  # Теперь переменная определена
        gridcolor="rgba(0,0,0,0.05)",
        zeroline=False,
        ),
        yaxis=dict(
            title="\u0420\u0430\u0437\u043d\u0438\u0446\u0430 \u0441\u0440\u0435\u0434\u043d\u0438\u0445 (\u0431\u0440\u0435\u043d\u0434 \u2212 \u043b\u0438\u0434\u0435\u0440)",
            range=[y_min, y_max],
            gridcolor="rgba(0,0,0,0.05)",
            zeroline=False,
        ),
        height=600,
        margin=dict(l=60, r=30, t=30, b=60),
        font=dict(family=font_family, size=font_px, color="#333333"),
        plot_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=True)

    # —— Таблица с деталями ——
    with st.expander("\u0414\u0435\u0442\u0430\u043b\u0438 \u043f\u043e \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u044f\u043c"):
        table_data = []
        for p in points_data:
            table_data.append({
                "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u044c": p["label"],
                "\u041a\u043e\u0440\u0440\u0435\u043b\u044f\u0446\u0438\u044f": round(p["corr"], 3),
                "\u0421\u0440\u0435\u0434\u043d\u0435\u0435 (\u0431\u0440\u0435\u043d\u0434)": round(p["mean_sel"], 3),
                "\u0421\u0440\u0435\u0434\u043d\u0435\u0435 (\u043b\u0438\u0434\u0435\u0440)": round(p["mean_leader"], 3),
                "\u0420\u0430\u0437\u043d\u0438\u0446\u0430": round(p["diff"], 3),
                "\u041b\u0438\u0434\u0435\u0440": fmt_brand(p["leader_brand"]),
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)


render = render_competitive_map
