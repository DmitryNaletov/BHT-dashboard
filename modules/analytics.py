import pandas as pd
import numpy as np
from scipy import stats


# ── Базовые статистики ─────────────────────────────────────

def weighted_mean(series, weights):
    return np.average(series, weights=weights)


def weighted_std(series, weights):
    m = weighted_mean(series, weights)
    var = np.average((series - m) ** 2, weights=weights)
    return np.sqrt(var)


# ── T-тест Уэлча ───────────────────────────────────────────

def t_test_vs_overall(group_mean, group_std, group_n,
                      overall_mean, overall_std, overall_n,
                      alpha=0.05):
    """Сравнение среднего бренда vs среднего по остальным брендам."""
    s1, s2 = group_std ** 2, overall_std ** 2
    n1, n2 = group_n, overall_n
    if n1 < 2 or n2 < 2:
        return False, None, 1.0
    if s1 == 0 and s2 == 0:
        return False, None, 1.0
    t = (group_mean - overall_mean) / np.sqrt(s1 / n1 + s2 / n2)
    df = (s1 / n1 + s2 / n2) ** 2 / ((s1 / n1) ** 2 / (n1 - 1) + (s2 / n2) ** 2 / (n2 - 1))
    p = 2 * (1 - stats.t.cdf(abs(t), df))
    is_sig = p < alpha
    direction = "up" if group_mean > overall_mean else "down" if group_mean < overall_mean else None
    return is_sig, direction, p


# ── Z-тест для долей ───────────────────────────────────────

def z_test_proportion(p1, n1, p2, n2, alpha=0.05):
    if n1 == 0 or n2 == 0:
        return False, None, 1.0
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return False, None, 1.0
    z = (p1 - p2) / se
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    is_sig = p < alpha
    direction = "up" if p1 > p2 else "down" if p1 < p2 else None
    return is_sig, direction, p


def z_test_proportions(p1, n1, p2, n2):
    """Возвращает z-score (без p-value). Для обратной совместимости."""
    if n1 == 0 or n2 == 0:
        return 0.0
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0
    return (p1 - p2) / se


# ── OLS без statsmodels ────────────────────────────────────

def ols_coef_with_penetration(df, x_var, y_var, weight_var):
    """Взвешенная регрессия y ~ x через numpy.linalg.solve."""
    sub = df[[x_var, y_var, weight_var]].dropna()
    if len(sub) < 3:
        return 0.0, 0.0
    w = sub[weight_var].values.astype(float)
    x = sub[x_var].values.astype(float)
    y = sub[y_var].values.astype(float)
    X = np.column_stack([np.ones(len(x)), x])
    W = np.diag(w)
    try:
        beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ y)
    except np.linalg.LinAlgError:
        return 0.0, 0.0
    coef = beta[1]
    penetration = len(sub) / len(df) if len(df) > 0 else 0.0
    return coef, penetration


# ── Форматирование ────────────────────────────────────────

def format_period(period, freq):
    if freq == "W":
        return str(period)
    elif freq == "M":
        month_names = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн",
                       "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
        return month_names[period.month - 1] + " " + str(period.year)[-2:]
    elif freq == "Q":
        return "Q" + str(period.quarter) + " " + str(period.year)[-2:]
    elif freq == "Y":
        return str(period.year)
    return str(period)


def fmt_brand_value(v, val_labels):
    key = str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v)
    return val_labels.get(key, str(v))


# ── Фильтрация числовых переменных ─────────────────────────

def group_numeric_vars(df, var_list):
    """Разделяет список переменных на множественные (multi) и обычные (single)."""
    multi, single = [], []
    for v in var_list:
        if v not in df.columns:
            continue
        if v.endswith(("_1", "_2", "_3", "_4", "_5", "_6", "_7", "_8", "_9", "_10",
                        "_11", "_12", "_13", "_14", "_15", "_16", "_17", "_18", "_19", "_20")):
            multi.append(v)
        else:
            single.append(v)
    return multi, single
