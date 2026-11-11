"""Vault identities and crash-safe local storage."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def vault_identity(vault):
    return str(Path(vault).resolve()).casefold()


def vault_key(vault):
    return hashlib.sha256(vault_identity(vault).encode("utf-8")).hexdigest()


def index_path(vault, data_dir=None):
    if data_dir is None:
        from nemo.core.paths import DATA_DIR
        data_dir = DATA_DIR
    return Path(data_dir) / "vaults" / vault_key(vault) / "index.json"


def atomic_json_write(destination, value):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=".nemo-", suffix=".tmp", delete=False) as file:
            name = file.name
            json.dump(value, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, destination)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def load_vault_index(path, vault=None):
    try:
        with open(path, encoding="utf-8") as file:
            value = json.load(file)
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        raise ValueError("The note index is damaged. Reindex this vault to rebuild it.")
    if "schema" in value:
        if value.get("schema") != 2 or not isinstance(value.get("notes"), dict):
            raise ValueError("Unsupported note index. Reindex this vault to rebuild it.")
        if vault and value.get("vault") != vault_identity(vault):
            raise ValueError("This note index belongs to a different vault.")
        value = value["notes"]
    if not all(isinstance(note, dict) and isinstance(note.get("text", ""), str)
               and isinstance(note.get("title"), str) for note in value.values()):
        raise ValueError("The note index is damaged. Reindex this vault to rebuild it.")
    return value
