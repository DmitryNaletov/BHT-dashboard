# modules/blocks/utils/sparkline.py
# -*- coding: utf-8 -*-

import html

import numpy as np
import pandas as pd


def generate_sparkline_svg(
    values,
    color="#333333",
    width=100,
    height=28,
    y_min=None,
    y_max=None,
):
    values = clean_sparkline_data(values)

    if not values:
        return '<div class="sparkline-empty">—</div>'

    # Диапазон передаётся извне, общий для группы метрик.
    if y_min is None:
        y_min = min(values)

    if y_max is None:
        y_max = max(values)

    if y_min == y_max:
        padding = abs(y_min) * 0.05 or 1.0
        y_min -= padding
        y_max += padding

    value_range = y_max - y_min

    values_for_line = values if len(values) > 1 else [values[0], values[0]]

    def y_coordinate(value):
        # Оставляем немного свободного пространства сверху и снизу.
        padding = 2
        usable_height = max(height - 2 * padding, 1)

        y = height - padding - (
            (value - y_min) / value_range
        ) * usable_height

        return min(max(y, padding), height - padding)

    # Одинаковые координаты для линии и точек.
    points = []

    for index, value in enumerate(values_for_line):
        x = index / (len(values_for_line) - 1) * width
        y = y_coordinate(value)
        points.append((x, y))

    path_data = "M" + " L".join(
        f"{x:.2f},{y:.2f}"
        for x, y in points
    )

    safe_color = html.escape(str(color), quote=True)

    svg = (
        f'<svg class="sparkline-svg" '
        f'viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" '
        f'aria-hidden="true">'
        f'<path d="{path_data}" '
        f'fill="none" '
        f'stroke="{safe_color}" '
        f'stroke-width="2" '
        f'stroke-linecap="round" '
        f'stroke-linejoin="round"/>'
        f'</svg>'
    )

    markers = []

    for index, value in enumerate(values_for_line):
        x_percent = (
            index / (len(values_for_line) - 1) * 100
        )

        # Тот же y_coordinate, что использован для SVG-линии.
        y_percent = y_coordinate(value) / height * 100

        tooltip = html.escape(f"Y = {value:.2f}", quote=True)

        markers.append(
            f'<span class="sparkline-marker" '
            f'style="left:{x_percent:.3f}%;top:{y_percent:.3f}%">'
            f'<span class="sparkline-dot" '
            f'style="background:{safe_color}"></span>'
            f'<span class="sparkline-tooltip">{tooltip}</span>'
            f'</span>'
        )

    return (
        '<div class="sparkline-plot">'
        f'{svg}'
        f'{"".join(markers)}'
        '</div>'
    )

def prepare_sparkline_html(
    values,
    color="#333333",
):
    svg = generate_sparkline_svg(
        values,
        color=color,
    )

    return (
        '<div class="sparkline-container">'
        f"{svg}"
        "</div>"
    )


def clean_sparkline_data(raw_data):
    """
    Преобразует входные данные в список конечных float-значений.
    """

    if raw_data is None:
        return []

    if isinstance(raw_data, str):
        raw_data = (
            raw_data
            .replace("\n", ",")
            .replace("\r", ",")
        )

        values = []

        for item in raw_data.split(","):
            item = item.strip()

            if not item:
                continue

            try:
                value = float(item)

                if np.isfinite(value):
                    values.append(value)

            except (TypeError, ValueError):
                continue

    elif isinstance(
        raw_data,
        (list, tuple, np.ndarray, pd.Series),
    ):
        values = []

        for item in raw_data:
            try:
                value = float(item)

                if np.isfinite(value):
                    values.append(value)

            except (TypeError, ValueError):
                continue

    else:
        try:
            value = float(raw_data)
            values = [value] if np.isfinite(value) else []
        except (TypeError, ValueError):
            values = []

    return values