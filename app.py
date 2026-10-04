# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os

from modules import auth, storage, spss_loader
from modules.blocks import block1_kpi_dynamics, block2_wordcloud, block3_multichoice, block4_competitive_map

try:
    from streamlit_user_device import user_device
    _device = user_device()
    is_mobile = _device in ["mobile", "tablet"]
except Exception:
    is_mobile = False

st.set_page_config(page_title="KPI Dashboard", layout="wide")

# —— Авторизация ———————————————————————————
if auth.get_role() is None:
    auth.login_page()
    st.stop()

role = auth.get_role()

# —— Супер-админ ——————————————————————————
if role == "super_admin":
    st.sidebar.markdown("**Роль:** SUPER ADMIN")
    if st.sidebar.button("Выйти"):
        auth.logout()
        st.rerun()
    auth.super_admin_page()
    st.stop()

# —— Обычный вход ——————————————————————————
tenant_id = auth.get_tenant_id()
if not tenant_id:
    st.error("Не определена компания. Войдите заново.")
    auth.logout()
    st.rerun()

# —— Боковая панель ——————————————————————————
st.sidebar.markdown(f"**Роль:** {role.upper()}")
st.sidebar.caption(f"Компания: `{tenant_id}`")
if st.sidebar.button("Выйти"):
    auth.logout()
    st.rerun()

if "uploader_counter" not in st.session_state:
    st.session_state["uploader_counter"] = 0

# —— Унифицированный размер шрифта ———————————————————
FONT_PX = 16

# —— Загрузка данных и конфига ———————————————————————
registry = storage.get_registry(tenant_id)
df = storage.load_dataset(tenant_id)
cfg = storage.load_config(tenant_id)
var_labels = storage.load_var_labels(tenant_id)
val_labels = storage.load_value_labels(tenant_id)

if "go_to_dashboard" not in st.session_state:
    st.session_state["go_to_dashboard"] = False


# —— Блок управления данными (только админ) ————————————————
if role == "admin":
    with st.sidebar.expander("Управление данными", expanded=(df is None)):
        if registry:
            st.markdown("**Загруженные файлы:**")
            for entry in registry:
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    st.write(f"\U0001F4C4 {entry['filename']}")
                    st.caption(f"{entry['rows']:,} записей · {entry['cols']} перем. · {entry['upload_date']}")
                with col_del:
                    if st.button("\u2716", key=f"del_{entry['filename']}", help=f"Удалить {entry['filename']}"):
                        storage.remove_file(tenant_id, entry["filename"])
                        st.rerun()
            st.divider()

        uploader_key = f"file_uploader_{st.session_state['uploader_counter']}"
        uploaded_file = st.file_uploader("Загрузить .sav", type=["sav"], key=uploader_key)
        if uploaded_file is not None:
            try:
                with st.spinner("Чтение SPSS-файла..."):
                    df_new, v_labels, vl_labels = spss_loader.read_sav_with_labels(uploaded_file)
                    storage.add_file(tenant_id, uploaded_file.name, df_new,
                                     var_labels=v_labels, val_labels=vl_labels)
                st.success(f"Файл \u00ab{uploaded_file.name}\u00bb загружен!")
                st.session_state["uploader_counter"] += 1
                st.rerun()
            except Exception as e:
                st.error(f"Ошибка чтения: {e}")

        if registry:
            if st.button("Сбросить все данные", type="secondary"):
                storage.reset_all(tenant_id)
                st.rerun()

# —— Если данных нет —————————————————————————————
if df is None:
    if role == "admin":
        st.info("Загрузите .sav-файл через панель \u00abУправление данными\u00bb слева.")
    else:
        st.warning("Данные не загружены. Обратитесь к администратору.")
    st.stop()

# —— Проверка конфига ———————————————————————————
required_keys = ["kpi_var", "brand_var", "weight_var", "date_var"]
config_ok = all(k in cfg and cfg[k] for k in required_keys)

# —— Навигация ————————————————————————————————
if role == "admin":
    pages = ["Дашборд", "Импорт/настройка"]
    if st.session_state["go_to_dashboard"]:
        st.session_state["go_to_dashboard"] = False
        default_page = "Дашборд"
    elif not config_ok:
        default_page = "Импорт/настройка"
    else:
        default_page = "Дашборд"
    page = st.sidebar.selectbox("Страница", pages,
                                index=pages.index(default_page),
                                key="page_nav")
else:
    page = "Дашборд"

# ═══════════════════════════════════════════════════════════
#  СТРАНИЦА: ИМПОРТ И НАСТРОЙКА
# ═══════════════════════════════════════════════════════════
if page == "Импорт/настройка" and role == "admin":
    st.header("Настройка переменных")
    st.write(f"**Записей:** {len(df):,} | **Переменных:** {len(df.columns)}")

    with st.expander("Превью данных (первые 5 строк)"):
        st.dataframe(df.head(), width="stretch")

    vars_list = df.columns.tolist()

    def display_name(var):
        label = var_labels.get(var, "")
        return f"{var} — {label}" if label else var

    display_vars = [display_name(v) for v in vars_list]
    name_to_display = dict(zip(vars_list, display_vars))
    display_to_name = dict(zip(display_vars, vars_list))

    def idx(key, default=0):
        var = cfg.get(key)
        if var and var in vars_list:
            return display_vars.index(name_to_display[var])
        return default

    st.subheader("Ключевые переменные")
    cfg["kpi_var"] = display_to_name[st.selectbox("Основной KPI (среднее или %)", display_vars, index=idx("kpi_var"))]
    cfg["brand_var"] = display_to_name[st.selectbox("Бренд (номинальная, 2-я после ID)", display_vars, index=idx("brand_var", 1))]
    cfg["weight_var"] = display_to_name[st.selectbox("Weight (вес для взвешивания)", display_vars, index=idx("weight_var", 2))]
    cfg["date_var"] = display_to_name[st.selectbox("Дата (динамика, формат даты SPSS)", display_vars, index=idx("date_var", 3))]

    st.subheader("Дополнительные переменные")
    cfg["comment_vars"] = [display_to_name[v] for v in st.multiselect(
        "Комментарии / множественные переменные (Q3, Q3_1, Q3_2...)",
        display_vars,
        default=[name_to_display[v] for v in cfg.get("comment_vars", []) if v in vars_list]
    )]
    cfg["extra_vars"] = [display_to_name[v] for v in st.multiselect(
        "Дополнительные показатели (среднее или %)",
        display_vars,
        default=[name_to_display[v] for v in cfg.get("extra_vars", []) if v in vars_list]
    )]
    cfg["filter_vars"] = [display_to_name[v] for v in st.multiselect(
        "Переменные для фильтров и разрезов",
        display_vars,
        default=[name_to_display[v] for v in cfg.get("filter_vars", []) if v in vars_list]
    )]

    # —— Цвета брендов ———————————————————————————
    st.subheader("Цвета брендов")
    brand_var_cfg = cfg.get("brand_var")
    if brand_var_cfg and brand_var_cfg in df.columns:
        unique_brands = sorted(df[brand_var_cfg].dropna().unique().tolist())
        vl_brands = val_labels.get(brand_var_cfg, {})
        def fmt_brand_cfg(v):
            key = str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v)
            return vl_brands.get(key, str(v))
        brand_colors_cfg = cfg.get("brand_colors", {})
        cols = st.columns(4)
        for i, brand_val in enumerate(unique_brands):
            col = cols[i % 4]
            label = fmt_brand_cfg(brand_val)
            key = str(int(brand_val)) if isinstance(brand_val, (int, float)) and float(brand_val).is_integer() else str(brand_val)
            default_color = brand_colors_cfg.get(key, "hsl(" + str(i * 60 % 360) + ", 70%, 50%)")
            brand_colors_cfg[key] = col.color_picker(label, default_color, key=f"brand_color_{i}")
        # Очистка старых дубликатов (например "1.0" когда нужно "1")
        valid_keys = {str(int(b)) if isinstance(b, (int, float)) and float(b).is_integer() else str(b) for b in unique_brands}
        brand_colors_cfg = {k: v for k, v in brand_colors_cfg.items() if k in valid_keys}
        cfg["brand_colors"] = brand_colors_cfg

    st.divider()

    if st.button("\U0001F4BE Сохранить настройки", type="primary"):
        storage.save_config(tenant_id, cfg)
        st.session_state["go_to_dashboard"] = True
        st.rerun()

    st.stop()

# ═══════════════════════════════════════════════════════════
#  СТРАНИЦА: ДАШБОРД
# ═══════════════════════════════════════════════════════════
if not config_ok:
    if role == "admin":
        st.warning("Сначала настройте переменные в разделе \u00abИмпорт/настройка\u00bb.")
    else:
        st.warning("Дашборд ещё не настроен администратором.")
    st.stop()

# —— Периодичность (в сайдбаре, выше фильтров) ————————————
st.sidebar.markdown("**Периодичность**")
freq_map = {"Неделя": "W", "Месяц": "M", "Квартал": "Q", "Год": "Y"}

# Восстановление из конфига через index (фикс сброса после перелогина)
freq_options = list(freq_map.keys())
saved_freq_label = cfg.get("_freq_label", "Месяц")
default_freq_idx = freq_options.index(saved_freq_label) if saved_freq_label in freq_options else 1

freq_sel = st.sidebar.selectbox("Периодичность", freq_options,
                                index=default_freq_idx,
                                key="global_freq_label")
freq = freq_map[freq_sel]
if cfg.get("_freq_label") != freq_sel:
    cfg["_freq_label"] = freq_sel
    storage.save_config(tenant_id, cfg)
st.session_state["global_freq"] = freq

# —— Глобальные фильтры ——————————————————————————————
st.sidebar.divider()
st.sidebar.markdown("**Фильтры**")

df_filtered = df.copy()
filter_vars = cfg.get("filter_vars", [])
for var in filter_vars:
    if var not in df.columns:
        continue
    unique_vals = sorted(df[var].dropna().unique().tolist())
    vl = val_labels.get(var, {})
    def fmt(v):
        key = str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v)
        return vl.get(key, str(v))
    display_options = [fmt(v) for v in unique_vals]
    sel_idx = st.sidebar.multiselect(
        f"{var}",
        range(len(unique_vals)),
        default=list(range(len(unique_vals))),
        format_func=lambda i: display_options[i],
        key=f"filter_{var}"
    )
    if sel_idx and len(sel_idx) < len(unique_vals):
        selected_vals = [unique_vals[i] for i in sel_idx]
        df_filtered = df_filtered[df_filtered[var].isin(selected_vals)]

if st.sidebar.button("\U0001F504 Сбросить фильтры"):
    for var in filter_vars:
        key = f"filter_{var}"
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

# —— Подготовка brand_colors —————————————————————————————
brand_var = cfg.get("brand_var")
brand_colors = cfg.get("brand_colors", {})
if brand_var and brand_var in df.columns:
    unique_brands = sorted(df[brand_var].dropna().unique().tolist())
    for i, bv in enumerate(unique_brands):
        key = str(int(bv)) if isinstance(bv, (int, float)) and float(bv).is_integer() else str(bv)
        if key not in brand_colors:
            brand_colors[key] = "hsl(" + str(i * 60 % 360) + ", 70%, 50%)"

# —— Блок 1: Динамика KPI —————————————————————————
kpi_label = var_labels.get(cfg.get("kpi_var", ""), cfg.get("kpi_var", ""))
st.header(f"Динамика {kpi_label}")

try:
    block1_kpi_dynamics.render_kpi_dynamics(
        df_filtered, cfg, freq=freq,
        var_labels=var_labels,
        val_labels=val_labels,
        brand_colors=brand_colors,
        font_px=FONT_PX,
        is_mobile=is_mobile
    )
except Exception as e:
    st.error(f"Ошибка при построении графика: {e}")
    with st.expander("Отладка"):
        import traceback
        st.code(traceback.format_exc())


# —— Блок 2: Облако слов —————————————————————————————
st.header("Облако слов — открытые вопросы")

comment_vars = cfg.get("comment_vars", [])
if comment_vars:
    try:
        block2_wordcloud.render_wordcloud_block(
            df_filtered, cfg,
            var_labels=var_labels,
            val_labels=val_labels,
            brand_colors=brand_colors,
            font_px=FONT_PX,
            freq=freq,
            is_mobile=is_mobile
        )
    except Exception as e:
        st.error(f"Ошибка облака слов: {e}")
        with st.expander("Отладка"):
            import traceback
            st.code(traceback.format_exc())
else:
    st.info("Облако слов недоступно — админ не выбрал открытые вопросы (comment_vars) в настройках.")

# —— Блок 3: Драйверы и барьеры ——————————————————————
st.header("Драйверы и барьеры")

try:
    block3_multichoice.render_multichoice_block(
        df_filtered, cfg,
        var_labels=var_labels,
        val_labels=val_labels,
        brand_colors=brand_colors,
        font_px=FONT_PX,
        freq=freq,
        is_mobile=is_mobile
    )
except Exception as e:
    st.error(f"Ошибка блока 3: {e}")
    with st.expander("Отладка"):
        import traceback
        st.code(traceback.format_exc())

# —— Блок 4: Конкурентная карта ——————————————————————
st.header("Конкурентная карта")

extra_vars = cfg.get("extra_vars", [])
if extra_vars:
    try:
        block4_competitive_map.render_competitive_map(
            df_filtered, cfg,
            var_labels=var_labels,
            val_labels=val_labels,
            brand_colors=brand_colors,
            font_px=FONT_PX,
            freq=freq,
            is_mobile=is_mobile
        )
    except Exception as e:
        st.error(f"Ошибка блока 4: {e}")
        with st.expander("Отладка"):
            import traceback
            st.code(traceback.format_exc())
else:
    st.info("Конкурентная карта недоступна — админ не выбрал дополнительные показатели (extra_vars) в настройках.")
