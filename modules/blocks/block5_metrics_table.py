# modules/blocks/block5_metrics_table.py
# -*- coding: utf-8 -*-

import html
import numpy as np
import pandas as pd

from .utils.sparkline import (
    generate_sparkline_svg,
    clean_sparkline_data,
)
from .block5_compute import normalize_key
from ..analytics import fmt_brand_value

def render_metrics_table(
    df: pd.DataFrame,
    cfg: dict,
    var_labels: dict,
    val_labels: dict,
    brand_colors: dict,
    font_px: int,
    freq: str,
    is_mobile: bool,
) -> str:
    """
    Формирует HTML-таблицу динамики основных показателей.
    """

    if df is None or df.empty:
        return '<div class="metrics-empty">Нет данных для отображения</div>'

    brand_var = cfg.get("brand_var")
    date_var = cfg.get("date_var")
    weight_var = cfg.get("weight_var")

    if not brand_var or brand_var not in df.columns:
        raise KeyError(
            f"Переменная бренда '{brand_var}' отсутствует в данных"
        )

    if not date_var or date_var not in df.columns:
        raise KeyError(
            f"Переменная даты '{date_var}' отсутствует в данных"
        )

    # Формируем список метрик.
    # Нельзя использовать все var_labels:
    # туда входят бренд, дата, вес и прочие служебные переменные.
    metric_vars = []

    kpi_var = cfg.get("kpi_var")
    if kpi_var and kpi_var in df.columns:
        metric_vars.append(kpi_var)

    for metric_var in cfg.get("extra_vars", []):
        if metric_var in df.columns and metric_var not in metric_vars:
            metric_vars.append(metric_var)

    if not metric_vars:
        return """
        <div class="metrics-empty">
            Не выбраны показатели для отображения.
            Настройте KPI или дополнительные показатели.
        </div>
        """

    work_df = df.copy()

    # Приводим дату к datetime
    work_df["_block5_date"] = pd.to_datetime(
        work_df[date_var],
        errors="coerce",
    )

    work_df = work_df.dropna(subset=["_block5_date", brand_var])

    if work_df.empty:
        return """
        <div class="metrics-empty">
            Не удалось определить даты для построения динамики.
        </div>
        """

    # Нормализуем частоту периода
    period_freq = normalize_period_freq(freq)

    work_df["_block5_period"] = (
        work_df["_block5_date"].dt.to_period(period_freq)
    )

    all_periods = sorted(
        work_df["_block5_period"].dropna().unique().tolist()
    )

    if not all_periods:
        return """
        <div class="metrics-empty">
            Нет периодов для отображения.
        </div>
        """

    unique_brands = (
        work_df[brand_var]
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    # Стабильная сортировка брендов
    unique_brands = sorted(unique_brands, key=lambda value: str(value))
    table_html = generate_styles(font_px)

    # На мобильном — до 4 брендов в одной таблице,
    # на desktop — до 10.
    brands_per_table = 4 if is_mobile else 10

    if len(unique_brands) > brands_per_table:
        brand_groups = [
            unique_brands[i:i + brands_per_table]
            for i in range(0, len(unique_brands), brands_per_table)
        ]
    else:
        brand_groups = [unique_brands]

    # Общие границы Y:
    # отдельный диапазон для KPI и общий — для всех extra_vars.
    metric_values = {}

    for metric_var in metric_vars:
        metric_values[metric_var] = {}

        for brand in unique_brands:
            metric_values[metric_var][brand] = compute_metric_series(
                df=work_df,
                metric_var=metric_var,
                brand_var=brand_var,
                brand_value=brand,
                all_periods=all_periods,
                weight_var=weight_var,
            )

    kpi_range = get_shared_y_range(
        [
            value
            for brand_values in metric_values.get(kpi_var, {}).values()
            for value in brand_values
        ]
    )

    extra_values = [
        value
        for metric_var in cfg.get("extra_vars", [])
        if metric_var in metric_values
        for brand_values in metric_values[metric_var].values()
        for value in brand_values
    ]
    extra_range = get_shared_y_range(extra_values)

    for group_index, brand_group in enumerate(brand_groups):
        if len(brand_groups) > 1:
            first_number = group_index * brands_per_table + 1
            last_number = first_number + len(brand_group) - 1

            table_html += (
                '<div class="brand-group-title">'
                f'Бренды {first_number}–{last_number}'
                '</div>'
            )

        table_html += generate_table_structure(
            df=work_df,
            metric_vars=metric_vars,
            var_labels=var_labels,
            unique_brands=brand_group,
            all_periods=all_periods,
            brand_var=brand_var,
            weight_var=weight_var,
            brand_colors=brand_colors,
            val_labels=val_labels,
            metric_values=metric_values,
            kpi_var=kpi_var,
            kpi_range=kpi_range,
            extra_range=extra_range,
        )
    return table_html

def normalize_period_freq(freq: str) -> str:
    """
    Приводит частоту к формату pandas Period.
    """

    mapping = {
        "W": "W-SUN",
        "M": "M",
        "Q": "Q",
        "Y": "Y",
        "A": "Y",
    }

    return mapping.get(freq, freq or "M")

def get_shared_y_range(values: list) -> tuple[float, float]:
    """
    Возвращает общий конечный диапазон Y.

    Игнорирует NaN и бесконечные значения.
    Если все значения одинаковые, добавляет небольшой отступ,
    чтобы точки не легли на границу графика.
    """

    valid_values = []

    for value in values:
        try:
            value = float(value)
            if np.isfinite(value):
                valid_values.append(value)
        except (TypeError, ValueError):
            continue

    if not valid_values:
        return 0.0, 1.0

    y_min = min(valid_values)
    y_max = max(valid_values)

    if y_min == y_max:
        padding = abs(y_min) * 0.05 or 1.0
        return y_min - padding, y_max + padding

    return y_min, y_max

def generate_table_structure(
    df: pd.DataFrame,
    metric_vars: list,
    var_labels: dict,
    unique_brands: list,
    all_periods: list,
    brand_var: str,
    weight_var: str,
    brand_colors: dict,
    val_labels: dict,
    metric_values: dict,
    kpi_var: str,
    kpi_range: tuple,
    extra_range: tuple,
) -> str:
    table = ['<table class="metrics-table">']

    table.append(
        generate_header(
            unique_brands=unique_brands,
            val_labels=val_labels,
            brand_var=brand_var,
        )
    )
    table.append("<tbody>")

    for metric_var in metric_vars:
        metric_name = var_labels.get(metric_var, metric_var)

        table.append(
            generate_row(
                metric_name=metric_name,
                metric_var=metric_var,
                df=df,
                unique_brands=unique_brands,
                all_periods=all_periods,
                brand_var=brand_var,
                weight_var=weight_var,
                brand_colors=brand_colors,
                metric_values=metric_values,
                y_range=kpi_range if metric_var == kpi_var else extra_range )
        )

    table.append("</tbody>")
    table.append("</table>")

    return "".join(table)


def generate_header(
    unique_brands: list,
    val_labels: dict,
    brand_var: str,
) -> str:
    """
    Формирует заголовок таблицы с отображаемыми лейблами брендов.
    """

    header = [
        "<thead>",
        "<tr>",
        '<th class="labels">Метрика</th>',
    ]

    brand_value_labels = val_labels.get(brand_var, {})

    for brand in unique_brands:
        brand_label = fmt_brand_value(
            brand,
            brand_value_labels,
        )

        header.append(
            f"<th>{html.escape(str(brand_label))}</th>"
        )

    header.extend([
        "</tr>",
        "</thead>",
    ])

    return "".join(header)


def generate_row(
    metric_name: str,
    metric_var: str,
    df: pd.DataFrame,
    unique_brands: list,
    all_periods: list,
    brand_var: str,
    weight_var: str,
    brand_colors: dict,
    metric_values: dict,
    y_range: tuple,
) -> str:
    row = [
        "<tr>",
        f'<td class="labels">{html.escape(str(metric_name))}</td>',
    ]

    for brand in unique_brands:
        values = metric_values.get(metric_var, {}).get(brand, [])
        row.append(
            generate_cell(
                brand=brand,
                values=values,
                brand_colors=brand_colors,
                y_range=y_range,
            )
        )
    row.append("</tr>")

    return "".join(row)


def compute_metric_series(
    df: pd.DataFrame,
    metric_var: str,
    brand_var: str,
    brand_value,
    all_periods: list,
    weight_var: str,
) -> list:
    """
    Расчёт агрегированного значения показателя
    по каждому периоду для конкретного бренда.
    """

    brand_df = df[df[brand_var] == brand_value]
    result = []

    for period in all_periods:
        period_df = brand_df[
            brand_df["_block5_period"] == period
        ].copy()

        if period_df.empty:
            result.append(np.nan)
            continue

        values = pd.to_numeric(
            period_df[metric_var],
            errors="coerce",
        )

        valid_mask = values.notna()

        if weight_var and weight_var in period_df.columns:
            weights = pd.to_numeric(
                period_df[weight_var],
                errors="coerce",
            )

            valid_mask &= weights.notna()

            values = values[valid_mask]
            weights = weights[valid_mask]

            if values.empty or weights.empty:
                result.append(np.nan)
                continue

            weight_sum = weights.sum()

            if not np.isfinite(weight_sum) or weight_sum == 0:
                result.append(np.nan)
                continue

            value = np.average(
                values.to_numpy(dtype=float),
                weights=weights.to_numpy(dtype=float),
            )
        else:
            values = values[valid_mask]

            if values.empty:
                result.append(np.nan)
                continue

            value = values.mean()

        result.append(
            float(value) if np.isfinite(value) else np.nan
        )

    return result


def generate_cell(
    brand,
    values: list,
    brand_colors: dict,
    y_range: tuple,
) -> str:
    cleaned_values = clean_sparkline_data(values)

    if not cleaned_values:
        return """
        <td class="metric-cell metric-empty-cell">
            —
        </td>
        """

    last_value = cleaned_values[-1]

    # В конфиге ключи сохранены через normalize_key()
    brand_key = normalize_key(brand)
    brand_color = brand_colors.get(brand_key, "#333333")

    sparkline_svg = generate_sparkline_svg(
        values=cleaned_values,
        color=brand_color,
        width=100,
        height=28,
        y_min=y_range[0],
        y_max=y_range[1],
    )

    return f"""
    <td class="metric-cell">
        <div class="metric-value">
            {last_value:.2f}
        </div>

        <div class="sparkline-container">
            {sparkline_svg}
        </div>
    </td>
    """

def generate_styles(font_px: int) -> str:
    return f"""
    <style>
        .metrics-table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            font-family: Inter, -apple-system,
                BlinkMacSystemFont, 'Segoe UI', Roboto,
                'Helvetica Neue', Arial, sans-serif;
            font-size: {font_px}px;
        }}

        .metrics-table th,
        .metrics-table td {{
            border: 1px solid #e0e0e0;
            padding: 8px;
        }}

        .metrics-table th {{
            background: #f7f9fb;
            font-weight: 600;
            text-align: center;
        }}

        .metrics-table {{
            width: 100%;
            max-width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            font-family: Inter, -apple-system,
                BlinkMacSystemFont, 'Segoe UI', Roboto,
                'Helvetica Neue', Arial, sans-serif;
            font-size: {font_px}px;
        }}

        .metrics-table th:first-child,
        .metrics-table td:first-child {{
            width: 25%;
            max-width: 25vw;
            overflow-wrap: anywhere;
            word-break: break-word;
        }}

        .brand-group-title {{
            margin: 18px 0 6px;
            font-weight: 600;
        }}

        .labels {{
            font-weight: 600;
            text-align: left;
        }}

        .metric-cell {{
            position: relative;
            height: 58px;
            min-width: 110px;
            vertical-align: middle;
            text-align: center;
            overflow: visible;
        }}

        .metric-value {{
            position: absolute;
            z-index: 2;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: rgba(0, 0, 0, 0.45);
            font-size: 14px;
            font-weight: 700;
            pointer-events: none;
            white-space: nowrap;
        }}

        .sparkline-container {{
            width: 100%;
            height: 42px;
        }}

        .sparkline-container svg {{
            width: 100%;
            height: 100%;
            display: block;
            overflow: visible;
        }}

        .sparkline-svg {{
            width: 100%;
            height: 100%;
            display: block;
            overflow: visible;
        }}

        .sparkline-path {{
            pointer-events: none;
        }}

        .sparkline-point {{
            transition:
                r 0.15s ease,
                opacity 0.15s ease;
        }}

        .sparkline-container {{
            width: 100%;
            height: 42px;
            overflow: visible;
        }}

        .sparkline-plot {{
            position: relative;
            width: 100%;
            height: 42px;
            overflow: visible;
        }}

        .sparkline-svg {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            display: block;
            overflow: visible;
        }}

        .sparkline-marker {{
            position: absolute;
            z-index: 3;
            width: 0;
            height: 0;
        }}

        .sparkline-dot {{
            position: absolute;
            left: 0;
            top: 0;
            width: 8px;
            height: 8px;
            border: 1px solid #ffffff;
            border-radius: 50%;
            transform: translate(-50%, -50%);
            box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.18);
        }}

        .sparkline-tooltip {{
            position: absolute;
            left: 50%;
            bottom: 9px;
            display: block;
            width: max-content;
            max-width: 120px;
            padding: 4px 7px;
            border-radius: 5px;
            background: rgba(30, 30, 30, 0.92);
            color: #ffffff;
            font-size: 11px;
            line-height: 1.2;
            white-space: nowrap;
            text-align: center;
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
            transform: translateX(-50%);
        }}

        .sparkline-marker:hover .sparkline-tooltip,
        .sparkline-marker:focus-within .sparkline-tooltip {{
            opacity: 1;
            visibility: visible;
        }}

        @media (hover: none) {{
            .sparkline-marker:active .sparkline-tooltip {{
                opacity: 1;
                visibility: visible;
            }}
        }}

        .sparkline-tooltip {{
            opacity: 0;
            pointer-events: none;
            fill: #222222;
            stroke: #ffffff;
            stroke-width: 3px;
            paint-order: stroke;
            font-size: 10px;
            font-weight: 700;
        }}

        .sparkline-point-group:hover .sparkline-tooltip,
        .sparkline-point-group:focus .sparkline-tooltip {{
            opacity: 1;
        }}

        .sparkline-point-group:focus .sparkline-point {{
            r: 5.5;
            stroke: #ffffff;
            stroke-width: 2;
        }}        

        .metric-empty-cell {{
            color: #999999;
            text-align: center;
        }}

        .metrics-empty {{
            padding: 16px;
            color: #777777;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
        }}
    </style>
    """
