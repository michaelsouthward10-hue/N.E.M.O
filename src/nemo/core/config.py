from copy import deepcopy

import yaml

from nemo.core.paths import CONFIG_DIR, CONFIG_PATH, DEFAULT_CONFIG_PATH

DEFAULT_SETTINGS = {
    "project": {"name": "NEMO", "version": "1.0.0"},
    "vault": {"path": ""},
    "ai": {"provider": "ollama", "endpoint": "http://localhost:11434", "model": "qwen3:8b"},
    "display": {"theme": "cyan"},
}


def load_settings():
    if not CONFIG_PATH.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if DEFAULT_CONFIG_PATH.exists() and DEFAULT_CONFIG_PATH != CONFIG_PATH:
            CONFIG_PATH.write_text(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            save_settings(DEFAULT_SETTINGS)

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    settings = deepcopy(DEFAULT_SETTINGS)
    if not isinstance(data, dict):
        return settings

    for section, values in data.items():
        if isinstance(values, dict) and isinstance(settings.get(section), dict):
            settings[section].update(values)
        else:
            settings[section] = values

    return settings


def save_settings(settings):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        yaml.safe_dump(settings, file, sort_keys=False, allow_unicode=True)
