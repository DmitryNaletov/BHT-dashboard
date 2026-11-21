import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..analytics import (
    fmt_brand_value,
    format_period,
    numeric_values_and_weights,
    significant_direction,
    weighted_group_stats,
    weighted_group_stats_from_df,
)

from ..config import (
    FONT_FAMILY,
    SETTINGS,
    get_font_size,
    get_text_color,
)


def _theme_backgrounds():
    """Цвета фона таблицы для текущей темы Streamlit."""
    is_dark = st.get_option("theme.base") == "dark"

    page_background = (
        st.get_option("theme.backgroundColor")
        or ("#0e1117" if is_dark else "#ffffff")
    )
    header_background = (
        st.get_option("theme.secondaryBackgroundColor")
        or ("#262730" if is_dark else "#f0f2f6")
    )

    return page_background, header_background


def _brand_key(value):
    """Нормализует числовые значения брендов для поиска цвета."""
    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    return str(value)


def _build_chart(
    df,
    cfg,
    freq,
    var_labels,
    val_labels,
    brand_colors,
    font_px,
    is_mobile,
):
    # Названия колонок и настройки отображения.
    kpi_var = cfg["kpi_var"]
    brand_var = cfg["brand_var"]
    weight_var = cfg["weight_var"]
    date_var = cfg["date_var"]

    text_color = get_text_color()
    value_font = get_font_size("value_label", is_mobile)
    tooltip_font = get_font_size("tooltip", is_mobile)
    axis_tick_font = get_font_size("axis_tick", is_mobile)
    base_font = get_font_size("base", is_mobile)

    positive_color = SETTINGS["colors"]["significance_positive"]
    negative_color = SETTINGS["colors"]["significance_negative"]

    # Подготовка данных: оставляем нужные колонки,
    # преобразуем даты и назначаем период.
    df_work = df[
        [kpi_var, brand_var, weight_var, date_var]
    ].copy()

    df_work = df_work.dropna(
        subset=[kpi_var, brand_var, date_var]
    )
    df_work[date_var] = pd.to_datetime(
        df_work[date_var],
        errors="coerce",
    )
    df_work = df_work.dropna(subset=[date_var])

    if df_work.empty:
        return go.Figure()

    df_work["_period"] = df_work[date_var].dt.to_period(freq)

    unique_brands = sorted(
        df_work[brand_var].dropna().unique().tolist(),
        key=str,
    )
    all_periods = sorted(df_work["_period"].dropna().unique().tolist())

    if not unique_brands or not all_periods:
        return go.Figure()

    # Подписи брендов и периодов.
    brand_value_labels = (val_labels or {}).get(brand_var, {})
    brand_names = [
        fmt_brand_value(brand, brand_value_labels)
        for brand in unique_brands
    ]
    period_labels = [
        format_period(period, freq)
        for period in all_periods
    ]

    vertical_text = len(all_periods) > 6
    n_brands = len(unique_brands)

    # Расчёт среднего, стандартного отклонения и базы
    # каждого бренда для каждого периода.
    results = {}
    stds_by_period = {}
    ns_by_period = {}

    for brand in unique_brands:
        brand_key = _brand_key(brand)
        brand_df = df_work[df_work[brand_var] == brand]

        results[brand_key] = []
        stds_by_period[brand_key] = []
        ns_by_period[brand_key] = []

        for period in all_periods:
            period_df = brand_df[brand_df["_period"] == period]

            # Подготовка числовых значений и весов
            # выполняется общей функцией из analytics.py.
            values, weights = numeric_values_and_weights(
                period_df,
                kpi_var,
                weight_var,
            )

            mean, std, n = weighted_group_stats(values, weights)

            results[brand_key].append(mean)
            stds_by_period[brand_key].append(std)
            ns_by_period[brand_key].append(n)

    # Значимость сравнения бренда со средним остальных брендов
    # рассчитывается отдельно для каждого периода.
    sig_vs_others = {
        _brand_key(brand): [None] * len(all_periods)
        for brand in unique_brands
    }

    for period_index, period in enumerate(all_periods):
        period_data = df_work[df_work["_period"] == period]

        for brand in unique_brands:
            brand_key = _brand_key(brand)
            brand_data = period_data[period_data[brand_var] == brand]
            others_data = period_data[period_data[brand_var] != brand]

            brand_stats = weighted_group_stats_from_df(
                brand_data,
                kpi_var,
                weight_var,
            )
            others_stats = weighted_group_stats_from_df(
                others_data,
                kpi_var,
                weight_var,
            )
            
            if brand_stats is None or others_stats is None:
                continue

            direction = significant_direction(
                brand_stats,
                others_stats,
            )

            if direction is not None:
                sig_vs_others[brand_key][period_index] = direction

    # Значимость динамики бренда между двумя последними периодами.
    # Она отвечает только за стрелку, не за цвет числа.
    sig_directions = {}

    for brand in unique_brands:
        brand_key = _brand_key(brand)

        if len(all_periods) < 2:
            sig_directions[brand_key] = None
            continue

        current_mean = results[brand_key][-1]
        previous_mean = results[brand_key][-2]
        current_std = stds_by_period[brand_key][-1]
        previous_std = stds_by_period[brand_key][-2]
        current_n = ns_by_period[brand_key][-1]
        previous_n = ns_by_period[brand_key][-2]

        if (
            current_n < 2
            or previous_n < 2
            or not np.isfinite(current_mean)
            or not np.isfinite(previous_mean)
            or not np.isfinite(current_std)
            or not np.isfinite(previous_std)
        ):
            sig_directions[brand_key] = None
            continue

        sig_directions[brand_key] = significant_direction(
            (
                current_mean,
                current_std,
                current_n,
            ),
            (
                previous_mean,
                previous_std,
                previous_n,
            ),
        )

    # Настройки высоты и места для подписей и легенды.
    fig = go.Figure()

    items_per_row = 3 if is_mobile else 5
    legend_rows = max(1, math.ceil(n_brands / items_per_row))

    if vertical_text:
        max_label_len = max(len(label) for label in period_labels)
        xaxis_space = max_label_len * base_font * 0.65 + 15
    else:
        xaxis_space = base_font + 15

    legend_height = legend_rows * (base_font + 8)
    top_margin = 20
    bottom_margin = int(xaxis_space + legend_height + 25)

    total_height = max(600, n_brands * 35 + 200)
    if vertical_text:
        total_height = max(total_height, 600 + xaxis_space * 0.4)

    plot_area_height = total_height - top_margin - bottom_margin
    if plot_area_height > 0:
        legend_y = -(xaxis_space + 8) / plot_area_height
    else:
        legend_y = -0.20

    # Добавление столбцов и подписей.
    # Цвет числа — значимость относительно остальных брендов
    # в том же периоде; стрелка — значимость динамики.
    colors = brand_colors or {}

    for index, brand in enumerate(unique_brands):
        brand_key = _brand_key(brand)
        brand_name = str(brand_names[index])

        if brand_name.strip().lower() == "undefined":
            brand_name = ""

        default_color = f"hsl({index * 60 % 360}, 70%, 50%)"
        brand_color = colors.get(brand_key, default_color)

        y_values = results[brand_key]
        text_values = []
        text_colors = []

        for period_index, value in enumerate(y_values):
            if not np.isfinite(value):
                text_values.append("")
                text_colors.append(text_color)
                continue

            value_label = f"{value:.1f}"

            # Число окрашивается по сравнению с другими брендами
            # в этом же периоде.
            cross_direction = sig_vs_others[brand_key][period_index]
            if cross_direction == "up":
                label_color = positive_color
            elif cross_direction == "down":
                label_color = negative_color
            else:
                label_color = text_color

            # Стрелка окрашивается отдельно по динамике
            # между двумя последними периодами.
            trend_direction = (
                sig_directions.get(brand_key)
                if period_index == len(y_values) - 1
                else None
            )

            if trend_direction == "up":
                arrow = (
                    f"<span style='color:{positive_color}'>▲</span><br>"
                )
            elif trend_direction == "down":
                arrow = (
                    f"<span style='color:{negative_color}'>▼</span><br>"
                )
            else:
                arrow = ""

            text_values.append(
                f"{arrow}"
                f"<span style='color:{label_color}'>{value_label}</span>"
            )
            text_colors.append(label_color)

        fig.add_trace(
            go.Bar(
                x=period_labels,
                y=y_values,
                customdata=ns_by_period[brand_key],
                name=brand_name or " ",
                marker_color=brand_color,
                text=text_values,
                hovertemplate=(
                    f"{brand_name}<br>"
                    "%{x}: %{y:.3g}<br>"
                    "N=%{customdata}"
                    "<extra></extra>"
                ),
                textposition="outside",
                textangle=270 if vertical_text else 0,
                textfont=dict(
                    size=value_font,
                    color=text_colors,
                    family=FONT_FAMILY,
                ),
                hoverlabel=dict(
                    font=dict(
                        family=FONT_FAMILY,
                        size=tooltip_font,
                        color=text_color,
                    )
                ),
            )
        )

    # Общий стиль графика, осей и легенды.
    fig.update_layout(
        barmode="group",
        font=dict(
            family=FONT_FAMILY,
            size=base_font,
            color=text_color,
        ),
        title=" ",
        xaxis=dict(
            tickangle=270 if vertical_text else 0,
            tickfont=dict(
                size=axis_tick_font,
                family=FONT_FAMILY,
                color=text_color,
            ),
        ),
        yaxis=dict(
            title=dict(text=" "),
            tickfont=dict(
                size=axis_tick_font,
                family=FONT_FAMILY,
                color=text_color,
            ),
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=legend_y,
            xanchor="center",
            x=0.5,
            font=dict(
                size=base_font,
                family=FONT_FAMILY,
                color=text_color,
            ),
        ),
        margin=dict(
            l=0,
            r=0,
            t=top_margin,
            b=bottom_margin,
        ),
        bargap=0.3,
        bargroupgap=0.15,
        height=total_height,
        showlegend=True,
    )

    return fig


def _build_table(
    df,
    cfg,
    freq,
    var_labels,
    val_labels,
    brand_colors,
    font_px,
    is_mobile=False,
):
    kpi_var = cfg["kpi_var"]
    brand_var = cfg["brand_var"]
    weight_var = cfg["weight_var"]
    date_var = cfg["date_var"]

    df_work = df[
        [kpi_var, brand_var, weight_var, date_var]
    ].copy()

    df_work = df_work.dropna(
        subset=[kpi_var, brand_var, date_var]
    )
    df_work[date_var] = pd.to_datetime(
        df_work[date_var],
        errors="coerce",
    )
    df_work = df_work.dropna(subset=[date_var])

    if df_work.empty:
        st.info("Нет данных для отображения таблицы.")
        return

    df_work["_period"] = df_work[date_var].dt.to_period(freq)

    unique_brands = sorted(
        df_work[brand_var].dropna().unique().tolist(),
        key=str,
    )
    if not unique_brands:
        st.info("Нет брендов для отображения таблицы.")
        return

    brand_value_labels = (val_labels or {}).get(brand_var, {})
    all_periods = sorted(df_work["_period"].dropna().unique().tolist())
    period_labels = [
        format_period(period, freq)
        for period in all_periods
    ]

    rows = []

    for brand in unique_brands:
        brand_df = df_work[df_work[brand_var] == brand]
        row = {
            "Бренд": fmt_brand_value(brand, brand_value_labels)
        }

        for period, period_label in zip(all_periods, period_labels):
            period_df = brand_df[brand_df["_period"] == period]

            if period_df.empty:
                row[period_label] = ""
                continue

            values, weights = numeric_values_and_weights(
                period_df,
                kpi_var,
                weight_var,
            )

            if len(values) and weights.sum() > 0:
                row[period_label] = (
                    f"{np.average(values, weights=weights):.2f}"
                )
            else:
                row[period_label] = ""

        rows.append(row)

    table_df = pd.DataFrame(rows)

    scale = SETTINGS["mobile_scale"] if is_mobile else 1.0
    table_font = get_font_size("metric", is_mobile)
    text_color = get_text_color()
    page_background, header_background = _theme_backgrounds()

    table_style = [
        {
            "selector": "th",
            "props": [
                ("background-color", header_background),
                ("color", text_color),
                ("font-family", FONT_FAMILY),
                ("font-size", f"{table_font}px"),
                ("font-weight", "bold"),
                ("border", "1px solid #808080"),
            ],
        },
        {
            "selector": "td",
            "props": [
                ("background-color", page_background),
                ("color", text_color),
                ("font-family", FONT_FAMILY),
                ("font-size", f"{table_font}px"),
                ("border", "1px solid #808080"),
            ],
        },
    ]

    styled_table = table_df.style.set_table_styles(table_style)

    st.dataframe(
        styled_table,
        use_container_width=True,
        hide_index=True,
    )


def render_kpi_dynamics(
    df,
    cfg,
    freq="M",
    var_labels=None,
    val_labels=None,
    brand_colors=None,
    font_px=16,
    is_mobile=False,
):
    interface_font = get_font_size("interface", is_mobile)

    st.markdown(
        f"""
        <style>
        div[role="radiogroup"] label {{
            font-family: {FONT_FAMILY};
            font-size: {interface_font}px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    view = st.radio(
        "Просмотр",
        ["График", "Таблица"],
        horizontal=True,
        key="b1_view",
    )

    if view == "График":
        fig = _build_chart(
            df,
            cfg,
            freq,
            var_labels,
            val_labels,
            brand_colors,
            font_px,
            is_mobile,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        _build_table(
            df,
            cfg,
            freq,
            var_labels,
            val_labels,
            brand_colors,
            font_px,
            is_mobile,
        )