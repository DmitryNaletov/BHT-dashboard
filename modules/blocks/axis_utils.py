import math


def calculate_x_range(corrs):
    """Расчет диапазона X"""
    if not corrs:
        return (-0.1, 0.1)
    adjusted_min = math.floor(min(corrs) * 10) / 10
    adjusted_max = math.ceil(max(corrs) * 10) / 10
    if adjusted_max - adjusted_min < 0.1:
        adjusted_max = adjusted_max + 0.1
    return (adjusted_min, adjusted_max)

def calculate_y_range(diffs):
    """Расчет диапазона Y"""
    if not diffs:
        return (-0.1, 0.1)
    adjusted_min = math.floor(min(diffs) * 10) / 10
    adjusted_max = math.ceil(max(diffs) * 10) / 10
    if adjusted_max - adjusted_min < 0.1:
        adjusted_max = adjusted_max + 0.1
    return (adjusted_min, adjusted_max)

def to_px(x, y, x_range, y_range, plot_w=800, plot_h=500):
    """Конвертация в пиксели"""
    x_span = x_range[1] - x_range[0]
    y_span = y_range[1] - y_range[0]
    return (
        (x - x_range[0]) / x_span * plot_w,
        plot_h - (y - y_range[0]) / y_span * plot_h
    )

def prepare_axes(corrs, diffs):
    """Подготовка осей"""
    x_range = calculate_x_range(corrs)
    y_range = calculate_y_range(diffs)
    return x_range, y_range
