import os
import pandas as pd
import json
import pickle
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

TENANTS_PATH = DATA_DIR / "tenants.json"
SESSION_PATH = DATA_DIR / "session.json"


# ── Реестр тенантов ──────────────────────────────────────────

def _default_tenants():
    return {
        "demo": {
            "name": "Demo Company",
            "admin_password": "admin123",
            "user_password": "user123"
        }
    }


def load_tenants():
    if not TENANTS_PATH.exists():
        save_tenants(_default_tenants())
    try:
        with open(TENANTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _default_tenants()


def save_tenants(tenants: dict):
    with open(TENANTS_PATH, "w", encoding="utf-8") as f:
        json.dump(tenants, f, ensure_ascii=False, indent=2)


def add_tenant(tenant_id, name, admin_password, user_password):
    tenants = load_tenants()
    tenants[tenant_id] = {
        "name": name,
        "admin_password": admin_password,
        "user_password": user_password
    }
    save_tenants(tenants)


def remove_tenant(tenant_id):
    tenants = load_tenants()
    if tenant_id in tenants:
        del tenants[tenant_id]
        save_tenants(tenants)
    # Удаляем данные тенанта
    tenant_dir = DATA_DIR / tenant_id
    if tenant_dir.exists():
        import shutil
        shutil.rmtree(tenant_dir)


# ── Пути для конкретного тенанта ──────────────────────────────

def _tenant_dir(tenant_id):
    d = DATA_DIR / tenant_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _files_dir(tenant_id):
    d = _tenant_dir(tenant_id) / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Реестр файлов ────────────────────────────────────────────

def get_registry(tenant_id):
    path = _files_dir(tenant_id) / "registry.json"
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_registry(tenant_id, registry):
    path = _files_dir(tenant_id) / "registry.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def add_file(tenant_id, filename, df, var_labels=None, val_labels=None):
    files_dir = _files_dir(tenant_id)
    safe_name = filename.replace(" ", "_").replace(".", "_")
    file_path = files_dir / f"{safe_name}.pkl"
    with open(file_path, "wb") as f:
        pickle.dump(df, f)

    registry = get_registry(tenant_id)
    registry = [r for r in registry if r["filename"] != filename]
    registry.append({
        "filename": filename,
        "storage_name": safe_name,
        "rows": len(df),
        "cols": len(df.columns),
        "upload_date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    })
    save_registry(tenant_id, registry)

    if var_labels:
        existing = load_var_labels(tenant_id)
        existing.update(var_labels)
        save_var_labels(tenant_id, existing)

    if val_labels:
        existing = load_value_labels(tenant_id)
        existing.update(val_labels)
        save_value_labels(tenant_id, existing)


def remove_file(tenant_id, filename):
    registry = get_registry(tenant_id)
    entry = next((r for r in registry if r["filename"] == filename), None)
    if entry:
        file_path = _files_dir(tenant_id) / f"{entry['storage_name']}.pkl"
        if file_path.exists():
            os.remove(file_path)
        registry = [r for r in registry if r["filename"] != filename]
        save_registry(tenant_id, registry)


def load_dataset(tenant_id):
    registry = get_registry(tenant_id)
    if not registry:
        return None
    dfs = []
    for entry in registry:
        file_path = _files_dir(tenant_id) / f"{entry['storage_name']}.pkl"
        if file_path.exists():
            try:
                with open(file_path, "rb") as f:
                    dfs.append(pickle.load(f))
            except Exception:
                pass
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


# ── Лейблы ───────────────────────────────────────────────────

def save_var_labels(tenant_id, labels: dict):
    path = _tenant_dir(tenant_id) / "var_labels.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)


def load_var_labels(tenant_id):
    path = _tenant_dir(tenant_id) / "var_labels.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_value_labels(tenant_id, labels: dict):
    path = _tenant_dir(tenant_id) / "value_labels.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(labels, f, ensure_ascii=False, indent=2)


def load_value_labels(tenant_id):
    path = _tenant_dir(tenant_id) / "value_labels.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ── Конфиг ───────────────────────────────────────────────────

def save_config(tenant_id, config: dict):
    path = _tenant_dir(tenant_id) / "config.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_config(tenant_id):
    path = _tenant_dir(tenant_id) / "config.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ── Полный сброс ─────────────────────────────────────────────

def reset_all(tenant_id):
    import shutil
    tenant_dir = _tenant_dir(tenant_id)
    if tenant_dir.exists():
        shutil.rmtree(tenant_dir)
    tenant_dir.mkdir(parents=True, exist_ok=True)
