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

# axis_utils.py
def add_quadrant_annotation(fig, x_min, x_max, y_min, y_max, corr_mean, text, x_anchor, y_anchor, color, font_family):
    x_pos = x_max - (x_max - corr_mean) * 0.03 if x_anchor == 'right' else x_min + (corr_mean - x_min) * 0.03
    y_pos = y_max - (y_max - 0) * 0.05 if y_anchor == 'top' else y_min + (0 - y_min) * 0.05
    
    fig.add_annotation(
        x=x_pos,
        y=y_pos,
        text=text,
        showarrow=False,
        font=dict(
            size=12, 
            color=f"rgba({color},0.8)", 
            family=font_family
        ),
        xanchor=x_anchor,
        yanchor=y_anchor
    )

