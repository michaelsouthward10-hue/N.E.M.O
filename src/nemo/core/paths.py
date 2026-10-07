import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNNING_FROM_SOURCE = (PROJECT_ROOT / "config" / "settings.yaml").is_file()

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    CONFIG_DIR = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming")) / "NEMO"
    DATA_DIR = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData/Local")) / "NEMO"
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
elif RUNNING_FROM_SOURCE:
    CONFIG_DIR = PROJECT_ROOT / "config"
    DATA_DIR = PROJECT_ROOT / "data"
    RESOURCE_DIR = PROJECT_ROOT
else:
    CONFIG_DIR = Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming")) / "NEMO"
    DATA_DIR = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData/Local")) / "NEMO"
    RESOURCE_DIR = Path(sys.prefix)

DOCS_DIR = PROJECT_ROOT / "docs"
LOGS_DIR = PROJECT_ROOT / "logs"

CONFIG_PATH = CONFIG_DIR / "settings.yaml"
DEFAULT_CONFIG_PATH = RESOURCE_DIR / "config" / "settings.yaml"
