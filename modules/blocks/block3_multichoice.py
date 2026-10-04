# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import re
import math
from collections import OrderedDict


def _brand_key(v):
    """Нормализованный ключ бренда: 1.0 -> '1', 2.0 -> '2', 'abc' -> 'abc'."""
    if isinstance(v, (int, float)) and float(v).is_integer():
        return str(int(v))
    return str(v)


def _group_vars(df, cfg):
    """Return only numeric (0/1) variables from comment_vars."""
    comment_vars = cfg.get("comment_vars", [])
    numeric_vars = []
    skipped = []
    for var in comment_vars:
        if var not in df.columns:
            continue
        if pd.api.types.is_numeric_dtype(df[var]):
            numeric_vars.append(var)
        else:
            skipped.append(var)
    return numeric_vars, skipped


def _z_test_proportions(p1, n1, p2, n2):
    if n1 == 0 or n2 == 0:
        return 0.0
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0
    return (p1 - p2) / se


def _format_period(period, freq):
    if freq == "W":
        return str(period)
    elif freq == "M":
        month_names = ["\u042f\u043d\u0432", "\u0424\u0435\u0432", "\u041c\u0430\u0440", "\u0410\u043f\u0440", "\u041c\u0430\u0439", "\u0418\u044e\u043d",
                       "\u0418\u044e\u043b", "\u0410\u0432\u0433", "\u0421\u0435\u043d", "\u041e\u043a\u0442", "\u041d\u043e\u044f", "\u0414\u0435\u043a"]
        return month_names[period.month - 1] + " " + str(period.year)[-2:]
    elif freq == "Q":
        return "Q" + str(period.quarter) + " " + str(period.year)[-2:]
    elif freq == "Y":
        return str(period.year)
    return str(period)


def _get_prefix(var):
    """Q3_1 -> Q3, Q3_2 -> Q3, Q10 -> Q10."""
    m = re.match(r'^(.+?)_\d+$', var)
    return m.group(1) if m else var


GRAY = "#999999"


def render_multichoice_block(df, cfg, var_labels=None, val_labels=None,
                             brand_colors=None, font_px=16, freq="M",
                             is_mobile=False):
    font_family = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"

    numeric_vars, skipped = _group_vars(df, cfg)

    if skipped:
        st.caption("\u0421\u0442\u0440\u043e\u043a\u043e\u0432\u044b\u0435 \u043f\u0435\u0440\u0435\u043c\u0435\u043d\u043d\u044b\u0435 (\u043e\u0442\u043a\u0440\u044b\u0442\u044b\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u044b) \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u044e\u0442\u0441\u044f \u0432 \u043e\u0431\u043b\u0430\u043a\u0435 \u0441\u043b\u043e\u0432: " + ", ".join(skipped))

    if not numeric_vars:
        st.info("\u0421\u0440\u0435\u0434\u0438 \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0445 \u043f\u0435\u0440\u0435\u043c\u0435\u043d\u043d\u044b\u0445 \u043d\u0435\u0442 \u0447\u0438\u0441\u043b\u043e\u0432\u044b\u0445 \u043c\u043d\u043e\u0436\u0435\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0445 \u0432\u043e\u043f\u0440\u043e\u0441\u043e\u0432 (0/1) \u0434\u043b\u044f \u0440\u0430\u0441\u0447\u0451\u0441\u043a\u0438.")
        return

    brand_var = cfg.get("brand_var")
    weight_var = cfg.get("weight_var")
    date_var = cfg.get("date_var")

    if not brand_var or brand_var not in df.columns:
        st.warning("\u0411\u0440\u0435\u043d\u0434 \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d.")
        return

    unique_brands = sorted(df[brand_var].dropna().unique().tolist())
    vl = val_labels or {}

    def fmt_brand(v):
        key = _brand_key(v)
        return vl.get(brand_var, {}).get(key, str(v))

    brand_names = [fmt_brand(b) for b in unique_brands]
    n_brands = len(unique_brands)

    # —— Группировка переменных по префиксу ——
    groups = OrderedDict()
    for var in numeric_vars:
        prefix = _get_prefix(var)
        if prefix not in groups:
            groups[prefix] = []
        groups[prefix].append(var)

    # —— Слайдер периодов (один раз) ——
    n_periods_sel = st.slider("\u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e \u043f\u0435\u0440\u0438\u043e\u0434\u043e\u0432", 1, 6, 3, key="mc_n_periods")

    # —— Определение периодов (один раз) ——
    has_dates = False
    periods = []
    if date_var and date_var in df.columns:
        df_temp = df.copy()
        df_temp[date_var] = pd.to_datetime(df_temp[date_var], errors="coerce")
        if df_temp[date_var].notna().sum() > 0:
            has_dates = True
            df_temp["_period"] = df_temp[date_var].dt.to_period(freq)
            all_periods = sorted(df_temp["_period"].dropna().unique().tolist())
            periods = all_periods[-n_periods_sel:] if len(all_periods) >= n_periods_sel else all_periods

    if not has_dates:
        periods = ["\u0412\u0441\u0435 \u0434\u0430\u043d\u043d\u044b\u0435"]

    period_labels = []
    for p in periods:
        if has_dates:
            period_labels.append(_format_period(p, freq))
        else:
            period_labels.append(str(p))

    n_p = len(period_labels)
    last_pi = n_p - 1

    # —— Цикл по группам префиксов ——
    for group_idx, (prefix, group_vars) in enumerate(groups.items()):
        # Метка группы
        var_labels_dict = var_labels or {}
        group_label = var_labels_dict.get(prefix, "")
        if not group_label:
            first_var = group_vars[0]
            group_label = var_labels_dict.get(first_var, prefix)

        st.markdown(f"**{group_label}**")

        # —— Расчёт процентов ——
        results = {}
        n_responses = {}

        for brand_val in unique_brands:
            brand_key = _brand_key(brand_val)
            results[brand_key] = {}
            n_responses[brand_key] = {}

            df_brand = df[df[brand_var] == brand_val].copy()

            if has_dates:
                df_brand[date_var] = pd.to_datetime(df_brand[date_var], errors="coerce")
                df_brand["_period"] = df_brand[date_var].dt.to_period(freq)

            for var in group_vars:
                results[brand_key][var] = {}
                n_responses[brand_key][var] = {}

                for pi, period in enumerate(periods):
                    if has_dates:
                        df_p = df_brand[df_brand["_period"] == period]
                    else:
                        df_p = df_brand

                    if weight_var and weight_var in df_p.columns:
                        weights = df_p[weight_var].fillna(1).values
                    else:
                        weights = np.ones(len(df_p))

                    col = df_p[var].fillna(0)
                    total_weight = weights.sum()
                    selected_weight = float((col.values * weights).sum()) if len(col) > 0 else 0.0

                    if total_weight > 0:
                        pct = selected_weight / total_weight * 100
                    else:
                        pct = 0.0

                    results[brand_key][var][pi] = pct
                    n_responses[brand_key][var][pi] = len(df_p)

        # —— Метки переменных ——
        var_display = []
        for var in group_vars:
            label = var_labels_dict.get(var, var)
            var_display.append(label if label else var)

        # —— Сортировка по убыванию (последний период, среднее по брендам) ——
        sort_vals = []
        for i, var in enumerate(group_vars):
            avg_last = np.mean([results[_brand_key(b)][var].get(last_pi, 0) for b in unique_brands])
            sort_vals.append((i, avg_last))
        sort_vals.sort(key=lambda x: -x[1])
        sorted_indices = [x[0] for x in sort_vals]

        sorted_vars = [group_vars[i] for i in sorted_indices]
        sorted_display = [var_display[i] for i in sorted_indices]

        n_cats = len(sorted_vars)

        # —— Y-позиционирование ——
        cat_step = n_p + 1
        tickvals = [i * cat_step + (n_p - 1) / 2 for i in range(n_cats)]

        # —— Subplot layout ——
        n_cols = min(n_brands, 6)
        n_rows = (n_brands + n_cols - 1) // n_cols

        subplot_titles = brand_names[:n_brands]

        fig = make_subplots(
            rows=n_rows, cols=n_cols,
            subplot_titles=subplot_titles,
            horizontal_spacing=0.06,
            vertical_spacing=0.12,
        )

        # —— Z-тесты для последнего периода ——
        brand_avg_colors = {}
        if n_brands >= 2:
            for brand_val in unique_brands:
                brand_key = _brand_key(brand_val)
                brand_avg_colors[brand_key] = {}
                for vi, var in enumerate(sorted_vars):
                    p1 = results[brand_key][var].get(last_pi, 0) / 100.0
                    n1 = n_responses[brand_key][var].get(last_pi, 0)
                    other_pcts = []
                    other_ns = []
                    for other_val in unique_brands:
                        if other_val == brand_val:
                            continue
                        ok = _brand_key(other_val)
                        other_pcts.append(results[ok][var].get(last_pi, 0) / 100.0)
                        other_ns.append(n_responses[ok][var].get(last_pi, 0))
                    total_other_n = sum(other_ns)
                    if total_other_n > 0:
                        p2 = sum(p * n for p, n in zip(other_pcts, other_ns)) / total_other_n
                    else:
                        p2 = 0
                    n2 = total_other_n
                    z = _z_test_proportions(p1, n1, p2, n2)
                    if z > 1.96:
                        brand_avg_colors[brand_key][vi] = "green"
                    elif z < -1.96:
                        brand_avg_colors[brand_key][vi] = "red"
                    else:
                        brand_avg_colors[brand_key][vi] = GRAY

        # —— Traces ——
        for brand_idx, brand_val in enumerate(unique_brands):
            brand_key = _brand_key(brand_val)
            brand_color = (brand_colors or {}).get(brand_key, "hsl(" + str(brand_idx * 60 % 360) + ", 70%, 50%)")

            row = brand_idx // n_cols + 1
            col = brand_idx % n_cols + 1

            for pi in range(n_p):
                is_last = (pi == n_p - 1)

                x_vals = []
                text_vals = []
                y_vals = []
                text_colors = []
                text_positions = []

                for i, var in enumerate(sorted_vars):
                    pct = results[brand_key][var].get(pi, 0)
                    x_vals.append(pct)
                    y_val = i * cat_step + (n_p - 1 - pi)
                    y_vals.append(y_val)

                    arrow = ""
                    if is_last and n_p >= 2:
                        prev_pi = n_p - 2
                        prev_pct = results[brand_key][var].get(prev_pi, 0)
                        n1_arr = n_responses[brand_key][var].get(pi, 0)
                        n2_arr = n_responses[brand_key][var].get(prev_pi, 0)
                        z = _z_test_proportions(pct / 100, n1_arr, prev_pct / 100, n2_arr)
                        if abs(z) > 1.96:
                            arrow = " \u25b2" if z > 0 else " \u25bc"

                    if is_last:
                        text_vals.append("{:.1f}%".format(pct) + arrow)
                        if n_brands >= 2 and brand_key in brand_avg_colors:
                            sig = brand_avg_colors[brand_key].get(i, GRAY)
                            text_colors.append(sig)
                        else:
                            text_colors.append(GRAY)
                    else:
                        text_vals.append("{:.1f}%".format(pct))
                        text_colors.append(GRAY)

                    if is_mobile:
                        text_positions.append("inside")
                    else:
                        if pct > 80:
                            text_positions.append("inside")
                        else:
                            text_positions.append("outside")

                if is_last:
                    marker = dict(color=brand_color, opacity=1.0)
                else:
                    marker = dict(color=brand_color, opacity=0.25)

                fig.add_trace(
                    go.Bar(
                        y=y_vals,
                        x=x_vals,
                        name=period_labels[pi],
                        orientation="h",
                        marker=marker,
                        width=0.8,
                        text=text_vals,
                        textposition=text_positions,
                        textfont=dict(size=font_px, color=text_colors, family=font_family),
                        insidetextanchor="start" if is_mobile else "end",
                        legendgroup=period_labels[pi],
                        showlegend=(brand_idx == 0),
                        hovertemplate=brand_names[brand_idx] + " \u00b7 " + period_labels[pi] +
                                      "<br>%{customdata}: %{x:.1f}%<extra></extra>",
                        customdata=sorted_display,
                    ),
                    row=row, col=col
                )

        # —— Оси ——
        for brand_idx in range(n_brands):
            row = brand_idx // n_cols + 1
            col = brand_idx % n_cols + 1

            show_labels = (col == 1)
            fig.update_yaxes(
                tickmode="array",
                tickvals=tickvals,
                ticktext=sorted_display if show_labels else [""] * len(tickvals),
                tickfont=dict(size=font_px, family=font_family),
                autorange="reversed",
                side="top" if is_mobile else "left",
                row=row, col=col,
            )
            fig.update_xaxes(
                tickfont=dict(size=font_px, family=font_family),
                title=dict(text="%" if brand_idx < n_cols else "", font=dict(size=font_px, family=font_family)),
                row=row, col=col,
            )

        total_height = max(400, n_cats * cat_step * 35 + 150)

        # —— Динамический расчёт отступа и легенды ——
        xaxis_tick_h = font_px + 10
        xaxis_title_h = font_px + 8
        xaxis_space = xaxis_tick_h + xaxis_title_h

        items_per_row = 6 if not is_mobile else 3
        n_legend_rows = math.ceil(n_p / items_per_row) if n_p > 0 else 1
        legend_h = n_legend_rows * (font_px + 8)

        margin_b = xaxis_space + legend_h + 25

        t_margin = 0 if is_mobile else 60
        plot_area_h = total_height - t_margin - margin_b
        if plot_area_h > 0:
            legend_y = -(xaxis_space + 8) / plot_area_h
        else:
            legend_y = -0.15

        if is_mobile:
            fig.update_layout(
                barmode="overlay",
                font=dict(family=font_family, size=font_px, color="black"),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=legend_y,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=font_px, family=font_family),
                ),
                margin=dict(l=0, r=0, t=0, b=margin_b),
                height=total_height,
                showlegend=True,
            )
        else:
            fig.update_layout(
                barmode="overlay",
                font=dict(family=font_family, size=font_px, color="black"),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=legend_y,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=font_px, family=font_family),
                ),
                margin=dict(l=50, r=0, t=t_margin, b=margin_b),
                height=total_height,
                showlegend=True,
            )

        st.plotly_chart(fig, use_container_width=True)
        if group_idx < len(groups) - 1:
            st.markdown("---")
