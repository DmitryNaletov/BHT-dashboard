# -*- coding: utf-8 -*-

import html
import re
from collections import OrderedDict

import numpy as np
import pandas as pd
import streamlit as st

from ..analytics import z_test_proportion


def _brand_key(value):
    """Нормализует ключ: 1.0 -> '1', 2.0 -> '2'."""
    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    return str(value)


def _group_vars(df, cfg):
    """
    Возвращает числовые переменные из comment_vars.

    Строковые переменные пропускаются — они могут использоваться
    в блоке облака слов.
    """
    numeric_vars = []
    skipped = []

    for var in cfg.get("comment_vars", []):
        if var not in df.columns:
            continue

        if pd.api.types.is_numeric_dtype(df[var]):
            numeric_vars.append(var)
        else:
            skipped.append(var)

    return numeric_vars, skipped


def _format_period(period, freq):
    """Форматирует период для легенды."""
    if freq == "W":
        return str(period)

    if freq == "M":
        month_names = [
            "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
            "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек",
        ]
        return (
            f"{month_names[period.month - 1]} "
            f"{str(period.year)[-2:]}"
        )

    if freq == "Q":
        return f"Q{period.quarter} {str(period.year)[-2:]}"

    if freq in ("Y", "A"):
        return str(period.year)

    return str(period)


def _get_prefix(var):
    """Q3_1 -> Q3, Q3_2 -> Q3, Q10 -> Q10."""
    match = re.match(r"^(.+?)_\d+$", var)
    return match.group(1) if match else var


def _safe_brand_color(color):
    """Разрешает только короткие и полные hex-цвета."""
    color = str(color or "").strip()

    if re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        return color

    if re.fullmatch(r"#[0-9a-fA-F]{3}", color):
        return color

    return "#4c78a8"


def _multichoice_styles(font_px):
    """CSS адаптивной сетки и полос показателей."""
    font_px = max(10, int(font_px))

    return f"""
    <style>
        .mc-section {{
            width: 100%;
            margin: 12px 0 24px;
            color: #263238;
            font-family: Inter, -apple-system, BlinkMacSystemFont,
                         'Segoe UI', Roboto, Arial, sans-serif;
            font-size: {font_px}px;
        }}

        /*
         * Левая колонка — ровно 25% ширины сетки.
         * Правая колонка — 75%, в ней располагаются бренды.
         */
        .mc-grid {{
            display: grid;
            grid-template-columns: 25% minmax(0, 75%);
            width: 100%;
            border-top: 1px solid #e0e0e0;
            border-left: 1px solid #e0e0e0;
        }}

        .mc-corner,
        .mc-brand-header,
        .mc-category-label,
        .mc-category-brands {{
            box-sizing: border-box;
            min-width: 0;
            border-right: 1px solid #e0e0e0;
            border-bottom: 1px solid #e0e0e0;
        }}

        .mc-corner,
        .mc-brand-header {{
            min-height: 48px;
            padding: 7px 5px;
            background: #f7f9fb;
            font-weight: 600;
            text-align: center;
            overflow-wrap: anywhere;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .mc-corner {{
            grid-column: 1;
        }}

        .mc-brand-headers {{
            grid-column: 2;
            display: grid;
            grid-template-columns:
                repeat(var(--mc-brand-count), minmax(0, 1fr));
            min-width: 0;
        }}

        .mc-category-label {{
            grid-column: 1;
            min-height: 74px;
            padding: 7px;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            text-align: left;
            overflow-wrap: anywhere;
            word-break: break-word;
        }}

        /*
         * Каждая строка категории — отдельная правая ячейка.
         * Внутри неё бренды могут переноситься на несколько рядов.
         * Высота левой метки автоматически растёт вместе с ячейкой.
         */
        .mc-category-brands {{
            grid-column: 2;
            display: grid;
            grid-template-columns:
                repeat(var(--mc-brand-count), minmax(0, 1fr));
            align-content: start;
            min-width: 0;
        }}

        .mc-brand-cell {{
            box-sizing: border-box;
            min-width: 0;
            min-height: 74px;
            padding: 5px 4px;
            border-right: 1px solid #e0e0e0;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 3px;
        }}

        .mc-brand-cell:last-child {{
            border-right: 0;
        }}

        .mc-category-brands .mc-brand-cell {{
            border-bottom: 0;
        }}

        .mc-period-bar {{
            position: relative;
            height: 22px;
            min-width: 0;
            overflow: hidden;
            background: #f1f3f5;
            border-radius: 2px;
        }}

        .mc-period-fill {{
            position: absolute;
            left: 1%;
            top: 0;
            bottom: 0;
            border-radius: 2px;
            opacity: var(--mc-opacity, 1);
        }}

        .mc-period-value {{
            position: absolute;
            z-index: 1;
            inset: 0 3px;
            display: flex;
            align-items: center;
            font-size: 10px;
            line-height: 1;
            font-weight: 600;
            white-space: normal;
            overflow-wrap: anywhere;
            pointer-events: none;
        }}

        .mc-period-value.mc-inside {{
            justify-content: flex-end;
            color: #ffffff;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.55);
        }}

        .mc-period-value.mc-outside {{
            justify-content: flex-start;
            color: #37474f;
        }}

        .mc-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px 16px;
            padding: 8px 4px 0;
            color: #4b5563;
            font-size: 12px;
        }}

        .mc-legend-item {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }}

        .mc-legend-swatch {{
            display: inline-block;
            width: 11px;
            height: 11px;
            border-radius: 2px;
        }}

        @media (max-width: 700px) {{
            .mc-section {{
                font-size: 12px;
            }}

            .mc-corner,
            .mc-brand-header {{
                min-height: 44px;
                padding: 5px 3px;
                font-size: 11px;
                line-height: 1.15;
            }}

            .mc-category-label {{
                min-height: 68px;
                padding: 5px;
                font-size: 11px;
                line-height: 1.2;
            }}

            .mc-brand-cell {{
                min-height: 68px;
                padding: 4px 2px;
                gap: 2px;
            }}

            .mc-period-bar {{
                height: 20px;
            }}

            .mc-period-value {{
                font-size: 9px;
            }}
        }}
        .mc-legend {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 8px 16px;
            width: 100%;
            padding: 10px 4px 0;
            color: #4b5563;
            font-size: 12px;
        }}
    </style>
    """

def _period_bar_html(
    pct,
    period_label,
    color,
    opacity,
    text_color,
    base_n,
    arrow="",
):
    """
    Создаёт HTML-полосу значения.

    В видимой подписи отображаются только процент и стрелка.
    Период и аналитическая база находятся во всплывающей подсказке.
    """
    pct = float(np.clip(pct, 0.0, 100.0))
    width_pct = max(0.0, pct - 1.0)

    value_class = "mc-inside" if pct >= 55 else "mc-outside"

    visible_label = html.escape(f"{pct:.1f}%{arrow}", quote=True)
    tooltip_period = html.escape(str(period_label), quote=True)
    tooltip_text = html.escape(
        f"{period_label}\n"
        f"Значение: {pct:.1f}%{arrow}\n"
        f"N = {base_n}",
        quote=True,
    )
    fill_color = _safe_brand_color(color)
    safe_text_color = html.escape(str(text_color), quote=True)
    opacity = float(np.clip(opacity, 0.15, 1.0))

    return (
        f'<div class="mc-period-bar" '
        f'title="{tooltip_text}">'
        f'<span class="mc-period-fill" '
        f'style="width:{width_pct:.3f}%;'
        f'background:{fill_color};'
        f'--mc-opacity:{opacity:.2f}"></span>'
        f'<span class="mc-period-value {value_class}" '
        f'style="color:{safe_text_color}">{visible_label}</span>'
        f'</div>'
    )

def render_multichoice_block(
    df,
    cfg,
    var_labels=None,
    val_labels=None,
    brand_colors=None,
    font_px=16,
    freq="M",
    is_mobile=False,
):
    """
    Отображает множественные показатели как HTML/CSS-сетку.

    Левая колонка занимает 25% ширины. Число брендовых колонок
    задаётся media query: до 10 на широком экране и до 4 на узком.
    """

    if df is None or df.empty:
        st.info("Нет данных для отображения.")
        return

    numeric_vars, skipped = _group_vars(df, cfg)

    if skipped:
        st.caption(
            "Строковые переменные пропущены в этом блоке: "
            + ", ".join(skipped)
        )

    if not numeric_vars:
        st.info(
            "Среди выбранных переменных нет числовых "
            "множественных вопросов (0/1)."
        )
        return

    brand_var = cfg.get("brand_var")
    weight_var = cfg.get("weight_var")
    date_var = cfg.get("date_var")

    if not brand_var or brand_var not in df.columns:
        st.warning("Бренд не настроен.")
        return

    brands = sorted(
        df[brand_var].dropna().unique().tolist(),
        key=lambda value: str(value),
    )

    if not brands:
        st.info("В данных не найдено брендов.")
        return

    var_labels = var_labels or {}
    val_labels = val_labels or {}
    brand_colors = brand_colors or {}

    brand_value_labels = val_labels.get(brand_var, {})

    def format_brand(value):
        key = _brand_key(value)
        return brand_value_labels.get(
            key,
            brand_value_labels.get(value, str(value)),
        )

    # Группировка вопросов по префиксу.
    question_groups = OrderedDict()
    for var in numeric_vars:
        question_groups.setdefault(_get_prefix(var), []).append(var)

    work_df = df.copy()
    has_dates = False

    if date_var and date_var in work_df.columns:
        work_df[date_var] = pd.to_datetime(
            work_df[date_var],
            errors="coerce",
        )

        if work_df[date_var].notna().any():
            has_dates = True
            work_df["_mc_period"] = work_df[date_var].dt.to_period(freq)

    if has_dates:
        all_periods = sorted(
            work_df["_mc_period"].dropna().unique().tolist()
        )

        if not all_periods:
            st.info("Нет периодов для отображения.")
            return

        max_periods = min(6, len(all_periods))

        n_periods_selected = st.slider(
            "Количество периодов",
            min_value=1,
            max_value=max_periods,
            value=min(3, max_periods),
            step=1,
            key=f"mc_n_periods_{brand_var}_{date_var or 'no_date'}",
        )

        periods = all_periods[-n_periods_selected:]
        period_labels = [
            _format_period(period, freq)
            for period in periods
        ]
    else:
        st.info("В данных нет дат для построения динамики.")
        return

    n_periods = len(periods)
    last_period_idx = n_periods - 1
    
    # CSS вставляется один раз перед таблицами блока.
    st.markdown(
        _multichoice_styles(font_px),
        unsafe_allow_html=True,
    )

    default_colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ]

    for question_idx, (prefix, question_vars) in enumerate(
        question_groups.items()
    ):
        question_label = (
            var_labels.get(prefix)
            or var_labels.get(question_vars[0])
            or prefix
        )

        st.markdown(f"**{html.escape(str(question_label))}**")

        # Результаты и размеры выборок.
        results = {}
        sample_sizes = {}

        for brand in brands:
            brand_key = _brand_key(brand)
            results[brand_key] = {}
            sample_sizes[brand_key] = {}

            brand_df = work_df[work_df[brand_var] == brand]

            for var in question_vars:
                results[brand_key][var] = {}
                sample_sizes[brand_key][var] = {}

                for period_idx, period in enumerate(periods):
                    if has_dates:
                        period_df = brand_df[
                            brand_df["_mc_period"] == period
                        ]
                    else:
                        period_df = brand_df

                    raw_values = pd.to_numeric(
                        period_df[var],
                        errors="coerce",
                    )
                    valid_mask = raw_values.notna()

                    values = raw_values[valid_mask].to_numpy(dtype=float)

                    if weight_var and weight_var in period_df.columns:
                        weights = pd.to_numeric(
                            period_df.loc[valid_mask, weight_var],
                            errors="coerce",
                        ).fillna(1).to_numpy(dtype=float)
                    else:
                        weights = np.ones(len(values), dtype=float)

                    total_weight = float(weights.sum())
                    selected_weight = (
                        float(np.dot(values, weights))
                        if len(values)
                        else 0.0
                    )

                    percentage = (
                        selected_weight / total_weight * 100.0
                        if total_weight > 0
                        else 0.0
                    )

                    results[brand_key][var][period_idx] = float(
                        np.clip(percentage, 0.0, 100.0)
                    )
                    sample_sizes[brand_key][var][period_idx] = len(values)

        # Сортируем категории по среднему проценту последнего периода.
        sorted_vars = sorted(
            question_vars,
            key=lambda var: -float(np.mean([
                results[_brand_key(brand)][var].get(
                    last_period_idx,
                    0.0,
                )
                for brand in brands
            ])),
        )

        # Межбрендовая значимость последнего периода:
        # бренд сравнивается с объединёнными остальными брендами.
        brand_significance = {}

        for brand in brands:
            brand_key = _brand_key(brand)
            brand_significance[brand_key] = {}

            for var in sorted_vars:
                if len(brands) < 2:
                    brand_significance[brand_key][var] = "#999999"
                    continue

                p_brand = (
                    results[brand_key][var].get(last_period_idx, 0.0)
                    / 100.0
                )
                n_brand = sample_sizes[brand_key][var].get(
                    last_period_idx,
                    0,
                )

                other_n = 0
                other_selected = 0.0

                for other_brand in brands:
                    if other_brand == brand:
                        continue

                    other_key = _brand_key(other_brand)
                    n_other = sample_sizes[other_key][var].get(
                        last_period_idx,
                        0,
                    )
                    p_other = (
                        results[other_key][var].get(last_period_idx, 0.0)
                        / 100.0
                    )

                    other_n += n_other
                    other_selected += p_other * n_other

                p_others = (
                    other_selected / other_n
                    if other_n > 0
                    else 0.0
                )

                is_sig, direction, _ = z_test_proportion(
                    p_brand,
                    n_brand,
                    p_others,
                    other_n,
                )

                if is_sig and direction == "up":
                    brand_significance[brand_key][var] = "green"
                elif is_sig and direction == "down":
                    brand_significance[brand_key][var] = "red"
                else:
                    brand_significance[brand_key][var] = "#999999"

        # Один HTML-блок содержит всю группу вопроса:
        # метки категорий, заголовки и брендовые ячейки.
        parts = [
            '<div class="mc-section">',
            '<div class="mc-grid">',
            '<div class="mc-corner">Показатель</div>',
            (
                '<div class="mc-brand-headers" '
                f'style="--mc-brand-count:{len(brands)}">'
            ),
        ]

        for brand in brands:
            brand_name = html.escape(str(format_brand(brand)))
            parts.append(
                f'<div class="mc-brand-header">{brand_name}</div>'
            )

        parts.append("</div>")  # mc-brand-headers

        for var in sorted_vars:
            category_label = html.escape(
                str(var_labels.get(var) or var)
            )

            parts.extend([
                '<div class="mc-category-label">',
                category_label,
                '</div>',
                (
                    '<div class="mc-category-brands" '
                    f'style="--mc-brand-count:{len(brands)}">'
                ),
            ])

            for brand_idx, brand in enumerate(brands):
                brand_key = _brand_key(brand)

                color = _safe_brand_color(
                    brand_colors.get(
                        brand_key,
                        default_colors[brand_idx % len(default_colors)],
                    )
                )

                bars = []

                for period_idx in reversed(range(n_periods)):
                    period_label = period_labels[period_idx]
                    percentage = results[brand_key][var].get(
                        period_idx,
                        0.0,
                    )

                    is_latest = period_idx == last_period_idx
                    opacity = 1.0 if is_latest else 0.35
                    arrow = ""

                    # Значимость изменения последнего периода
                    # относительно предыдущего.
                    if is_latest and n_periods >= 2:
                        previous_idx = period_idx - 1
                        previous_percentage = results[brand_key][var].get(
                            previous_idx,
                            0.0,
                        )

                        n_current = sample_sizes[brand_key][var].get(
                            period_idx,
                            0,
                        )
                        n_previous = sample_sizes[brand_key][var].get(
                            previous_idx,
                            0,
                        )

                        is_change_sig, change_direction, _ = (
                            z_test_proportion(
                                percentage / 100.0,
                                n_current,
                                previous_percentage / 100.0,
                                n_previous,
                            )
                        )

                        if is_change_sig and change_direction == "up":
                            arrow = " ▲"
                        elif (
                            is_change_sig
                            and change_direction == "down"
                        ):
                            arrow = " ▼"

                    if is_latest:
                        text_color = brand_significance[brand_key][var]
                    else:
                        text_color = "#37474f"

                    base_n = sample_sizes[brand_key][var].get(period_idx, 0)

                    bars.append(
                        _period_bar_html(
                            pct=percentage,
                            period_label=period_label,
                            color=color,
                            opacity=opacity,
                            text_color=text_color,
                            base_n=base_n,
                            arrow=arrow,
                        )
                    )

                parts.append(
                    '<div class="mc-brand-cell">'
                    + "".join(bars)
                    + '</div>'
                )

            parts.append("</div>")  # mc-category-brands

        # Легенда периодов.
        # Закрываем сетку до легенды,
        # чтобы она располагалась под всей таблицей.
        parts.append("</div>")  # mc-grid

        # Легенда занимает всю ширину и центрируется CSS-ом.
        parts.append('<div class="mc-legend">')

        # Периоды в легенде показываем от старого к новому.
        for period_idx, period_label in enumerate(period_labels):
            opacity = "1" if period_idx == last_period_idx else "0.35"

            parts.append(
                '<span class="mc-legend-item">'
                '<span class="mc-legend-swatch" '
                f'style="background:#4c78a8;opacity:{opacity}">'
                '</span>'
                f'{html.escape(str(period_label))}'
                '</span>'
            )

        parts.extend([
            "</div>",  # mc-legend
            "</div>",  # mc-section
        ])

        st.markdown(
            "".join(parts),
            unsafe_allow_html=True,
        )

        if question_idx < len(question_groups) - 1:
            st.markdown("---")