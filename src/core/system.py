from .config import load_settings
from pathlib import Path
import requests
from .scanner import VaultScanner
from ai.summarizer import Summarizer
import inspect

class SystemManager:

    def __init__(self):
        self.settings = load_settings()
        self.ai = Summarizer(
            self.settings["ai"]["endpoint"],
            self.settings["ai"]["model"]
        )

    def scan_vault(self):
        # instantiate and run the vault scanner
        scanner = VaultScanner(
            self.settings["vault"]["path"],
            self.ai,
        )

        return scanner.scan()

    def check_vault(self):
        vault = Path(self.settings["vault"]["path"])
        return vault.exists()

    def check_ollama(self):
        try:
            response = requests.get(
                self.settings["ai"]["endpoint"],
                timeout=2
            )
            return response.status_code == 200
        except Exception:
            return False

    def status(self):
        return {
            "vault": self.check_vault(),
            "ollama": self.check_ollama(),
        }