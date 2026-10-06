# -*- coding: utf-8 -*-
import streamlit as st
import json
import os
from pathlib import Path
from modules import storage

SUPER_ADMIN_PASSWORD = st.secrets.get("SUPER_ADMIN_PASSWORD", "")

SESSION_PATH = Path("data") / "session.json"


def get_role():
    if "role" not in st.session_state:
        st.session_state.role = None
    if st.session_state.role is None and SESSION_PATH.exists():
        try:
            with open(SESSION_PATH, "r") as f:
                data = json.load(f)
                st.session_state.role = data.get("role")
                st.session_state.tenant_id = data.get("tenant_id")
        except Exception:
            pass
    return st.session_state.role


def get_tenant_id():
    return st.session_state.get("tenant_id")


def login_page():
    st.title("Вход в дашборд")

    tab_login, tab_super = st.tabs(["Вход в компанию", "Супер-админ"])

    # ── Вкладка: вход в компанию ──
    with tab_login:
        tenants = storage.load_tenants()
        tenant_ids = list(tenants.keys())

        if not tenant_ids:
            st.warning("Нет зарегистрированных компаний. Обратитесь к супер-админу.")
            return

        tenant_id = st.selectbox(
            "Компания",
            tenant_ids,
            format_func=lambda t: tenants[t].get("name", t),
            key="login_tenant"
        )
        pwd = st.text_input("Пароль", type="password", key="login_pwd")

        if st.button("Войти", type="primary"):
            tenant = tenants[tenant_id]
            if pwd == tenant.get("admin_password"):
                _set_session("admin", tenant_id)
                st.rerun()
            elif pwd == tenant.get("user_password"):
                _set_session("user", tenant_id)
                st.rerun()
            else:
                st.error("Неверный пароль")

    # ── Вкладка: супер-админ ──
    with tab_super:
        super_pwd = st.text_input("Пароль супер-админа", type="password", key="super_pwd")
        if st.button("Войти как супер-админ", type="primary"):
            if super_pwd == SUPER_ADMIN_PASSWORD:
                _set_session("super_admin", None)
                st.rerun()
            else:
                st.error("Неверный пароль")


def super_admin_page():
    st.title("Управление компаниями")
    tenants = storage.load_tenants()

    st.subheader("Существующие компании")
    if tenants:
        for tid, info in tenants.items():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{info['name']}** (`{tid}`)")
                st.caption(f"Admin: {info['admin_password']} | User: {info['user_password']}")
            with col2:
                if st.button("Изменить", key=f"edit_{tid}"):
                    st.session_state[f"editing_{tid}"] = True
                    st.rerun()
            with col3:
                if st.button("Удалить", key=f"del_{tid}"):
                    storage.remove_tenant(tid)
                    st.rerun()

            if st.session_state.get(f"editing_{tid}"):
                with st.expander("Редактировать", expanded=True):
                    new_name = st.text_input("Название", value=info["name"], key=f"name_{tid}")
                    new_admin = st.text_input("Пароль admin", value=info["admin_password"], key=f"apwd_{tid}")
                    new_user = st.text_input("Пароль user", value=info["user_password"], key=f"upwd_{tid}")
                    if st.button("Сохранить", key=f"save_{tid}"):
                        storage.add_tenant(tid, new_name, new_admin, new_user)
                        st.session_state[f"editing_{tid}"] = False
                        st.rerun()
    else:
        st.info("Компаний пока нет.")

    st.divider()
    st.subheader("Добавить компанию")
    new_id = st.text_input("ID компании (латиница, без пробелов)", key="new_tid")
    new_name = st.text_input("Название", key="new_tname")
    new_admin_pwd = st.text_input("Пароль admin", key="new_apwd")
    new_user_pwd = st.text_input("Пароль user", key="new_upwd")
    if st.button("Добавить", type="primary", key="add_tenant"):
        if new_id and new_name and new_admin_pwd and new_user_pwd:
            if new_id in tenants:
                st.error("Компания с таким ID уже существует")
            else:
                storage.add_tenant(new_id, new_name, new_admin_pwd, new_user_pwd)
                st.success(f"Компания «{new_name}» добавлена")
                st.rerun()
        else:
            st.error("Заполните все поля")


def logout():
    st.session_state.role = None
    st.session_state.tenant_id = None
    if SESSION_PATH.exists():
        os.remove(SESSION_PATH)


def _set_session(role, tenant_id):
    st.session_state.role = role
    st.session_state.tenant_id = tenant_id
    os.makedirs("data", exist_ok=True)
    with open(SESSION_PATH, "w") as f:
        json.dump({"role": role, "tenant_id": tenant_id}, f)


def require_admin(func):
    def wrapper(*args, **kwargs):
        if get_role() not in ("admin", "super_admin"):
            st.warning("Доступ только для администратора")
            return None
        return func(*args, **kwargs)
    return wrapper
