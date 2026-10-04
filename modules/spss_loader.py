import pyreadstat
import pandas as pd


def _normalize_key(k):
    """Приводит код значения к единому строковому формату."""
    if isinstance(k, (int, float)) and float(k).is_integer():
        return str(int(k))
    return str(k)


def read_sav_with_labels(path):
    df, meta = pyreadstat.read_sav(path)

    # Метки переменных: {var_name: "Текст вопроса"}
    if hasattr(meta, "variable_label"):
        variable_labels = meta.variable_label or {}
    elif hasattr(meta, "column_labels"):
        variable_labels = dict(zip(df.columns, meta.column_labels))
    else:
        variable_labels = {col: col for col in df.columns}

    # Метки значений: конвертируем в {var_name: {code: label}}
    value_labels = {}
    if hasattr(meta, "value_labels") and hasattr(meta, "variable_to_label"):
        v2l = meta.variable_to_label or {}
        vl = meta.value_labels or {}
        for var_name, label_set_name in v2l.items():
            if label_set_name in vl:
                value_labels[var_name] = {
                    _normalize_key(k): v for k, v in vl[label_set_name].items()
                }
    elif hasattr(meta, "value_labels"):
        raw = meta.value_labels or {}
        for key, mapping in raw.items():
            value_labels[key] = {
                _normalize_key(k): v for k, v in mapping.items()
            }

    return df, variable_labels, value_labels
