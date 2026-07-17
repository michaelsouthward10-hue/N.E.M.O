from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]

CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def load_settings():
    print(f"Loading settings from: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    print("Settings loaded:")
    print(data)

    return data