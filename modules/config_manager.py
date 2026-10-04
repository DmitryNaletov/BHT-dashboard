from modules import storage


def get_config(tenant_id):
    return storage.load_config(tenant_id)


def set_config(tenant_id, cfg: dict):
    storage.save_config(tenant_id, cfg)


def is_config_ready(tenant_id):
    cfg = get_config(tenant_id)
    required = ["kpi_var", "brand_var", "weight_var", "date_var",
                "comment_vars", "extra_vars", "filter_vars"]
    return all(k in cfg for k in required)
