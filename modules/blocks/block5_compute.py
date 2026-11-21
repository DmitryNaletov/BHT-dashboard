# -*- coding: utf-8 -*-
"""Вычислительные функции для блока 5 (метрики-таблица)."""
import numpy as np
import pandas as pd
from ..analytics import t_test_vs_overall, weighted_std


def normalize_key(v):
    if isinstance(v, (int, float)) and float(v).is_integer():
        return str(int(v))
    return str(v)

def compute_metric_series(
    df,
    metric_var,
    brand_var,
    brand_val,
    all_periods,
    weight_var,
    date_var,
    freq,
):
    """
    Рассчитывает показатель по периодам для одного бренда.
    """

    work_df = df.copy()

    if metric_var not in work_df.columns:
        return [np.nan] * len(all_periods)

    if brand_var not in work_df.columns:
        return [np.nan] * len(all_periods)

    if date_var not in work_df.columns:
        return [np.nan] * len(all_periods)

    work_df["_block5_date"] = pd.to_datetime(
        work_df[date_var],
        errors="coerce",
    )

    work_df = work_df[
        work_df[brand_var] == brand_val
    ]

    work_df = work_df.dropna(
        subset=["_block5_date", metric_var]
    )

    work_df["_block5_period"] = (
        work_df["_block5_date"].dt.to_period(freq)
    )

    result = []

    for period in all_periods:
        period_df = work_df[
            work_df["_block5_period"] == period
        ]

        values = pd.to_numeric(
            period_df[metric_var],
            errors="coerce",
        )

        values = values.replace(
            [np.inf, -np.inf],
            np.nan,
        ).dropna()

        if values.empty:
            result.append(np.nan)
            continue

        if (
            weight_var
            and weight_var in period_df.columns
        ):
            weights = pd.to_numeric(
                period_df.loc[values.index, weight_var],
                errors="coerce",
            )

            valid = (
                values.notna()
                & weights.notna()
                & np.isfinite(weights)
            )

            values = values[valid]
            weights = weights[valid]

            if values.empty or weights.sum() == 0:
                result.append(np.nan)
                continue

            result.append(
                float(
                    np.average(
                        values.to_numpy(),
                        weights=weights.to_numpy(),
                    )
                )
            )
        else:
            result.append(float(values.mean()))

    return result

def compute_significance(df_work, metric_var, brand_var, weight_var, all_periods,date_var):
    """Значимость между брендами в последнем периоде (t-тест Уэлча).
    Возвращает dict: brand_key -> (direction|None, color).
    """
    sig = {}
    last_period = all_periods[-1]
    df_last = df_work[df_work[date_var].dt.to_period('M') == last_period]
    unique_brands = sorted(df_last[brand_var].unique().tolist())

    for brand_val in unique_brands:
        key = normalize_key(brand_val)
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


def compute_dynamics_significance(df_work, metric_var, brand_var, weight_var, all_periods, date_var):
    """Значимость динамики: последний период vs предпоследний (t-тест Уэлча).
    Возвращает dict: brand_key -> direction|None.
    """
    sig = {}
    unique_brands = sorted(df_work[brand_var].unique().tolist())

    if len(all_periods) < 2:
        for brand_val in unique_brands:
            sig[normalize_key(brand_val)] = None
        return sig

    last_period = all_periods[-1]
    prev_period = all_periods[-2]

    df_last = df_work[df_work[date_var].dt.to_period('M') == last_period]
    df_prev = df_work[df_work[date_var].dt.to_period('M') == prev_period]

    for brand_val in unique_brands:
        key = normalize_key(brand_val)

        df_b_last = df_last[df_last[brand_var] == brand_val]
        df_b_prev = df_prev[df_prev[brand_var] == brand_val]

        if len(df_b_last) < 2 or len(df_b_prev) < 2:
            sig[key] = None
            continue

        w_last = df_b_last[weight_var].fillna(1).values
        v_last = df_b_last[metric_var].values
        w_prev = df_b_prev[weight_var].fillna(1).values
        v_prev = df_b_prev[metric_var].values

        if w_last.sum() == 0 or w_prev.sum() == 0:
            sig[key] = None
            continue

        m_last = np.average(v_last, weights=w_last)
        m_prev = np.average(v_prev, weights=w_prev)
        s_last = weighted_std(v_last, w_last)
        s_prev = weighted_std(v_prev, w_prev)
        n_last = len(df_b_last)
        n_prev = len(df_b_prev)

        is_sig, direction, _ = t_test_vs_overall(m_last, s_last, n_last, m_prev, s_prev, n_prev)
        if is_sig and direction == "up":
            sig[key] = "up"
        elif is_sig and direction == "down":
            sig[key] = "down"
        else:
            sig[key] = None

    return sig

def prepare_sparkline_data(df_work, metric_var, brand_var, weight_var, all_periods, date_var):
    """
    Подготавливает данные для спарклайнов по всем брендам и метрикам
    """
    unique_brands = sorted(df_work[brand_var].unique().tolist())
    brand_keys = [normalize_key(b) for b in unique_brands]
    
    # Собираем данные по брендам
    brand_series = {}
    for brand_val in unique_brands:
        series = compute_metric_series(
            df_work, metric_var, brand_var, brand_val, 
            all_periods, weight_var, date_var
        )
        brand_series[normalize_key(brand_val)] = series
    
    return brand_series, brand_keys


def get_metric_sparkline_data(df_work, metric_var, brand_var, weight_var, all_periods, date_var):
    """
    Возвращает данные для спарклайна конкретной метрики по всем брендам
    """
    print("Запуск get_metric_sparkline_data")  # Отладка
    print(f"Переданные параметры:")
    print(f"df_work не пустой: {len(df_work) > 0}")
    print(f"metric_var: {metric_var}")
    print(f"brand_var: {brand_var}")
    print(f"weight_var: {weight_var}")
    print(f"all_periods: {all_periods}")
    print(f"date_var: {date_var}")

    brand_series, brand_keys = prepare_sparkline_data(
        df_work, metric_var, brand_var, weight_var, 
        all_periods, date_var
    )
    
    result = {}
    for key in brand_keys:
        # Очищаем NaN и возвращаем только валидные числа
        clean_data = [v for v in brand_series[key] if not np.isnan(v)]
        if len(clean_data) > 1:
            result[key] = clean_data
    
    return result