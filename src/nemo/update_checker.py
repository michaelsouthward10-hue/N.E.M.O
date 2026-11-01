"""Check the public NEMO GitHub releases for a newer version."""

import re

import requests

from nemo.version import APP_VERSION


RELEASE_URL = "https://api.github.com/repos/michaelsouthward10-hue/N.E.M.O/releases/latest"


def _version_parts(value):
    """Return numeric version components, ignoring a leading v and suffix."""
    match = re.search(r"\d+(?:\.\d+)*", str(value))
    if not match:
        return ()
    return tuple(int(part) for part in match.group().split("."))


def check_for_update():
    """Return release details when GitHub has a newer published version."""
    response = requests.get(
        RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "NEMO-desktop"},
        timeout=8,
    )
    response.raise_for_status()
    release = response.json()
    latest = release.get("tag_name", "")
    if not latest or _version_parts(latest) <= _version_parts(APP_VERSION):
        return None
    return {
        "current_version": APP_VERSION,
        "latest_version": latest.lstrip("vV"),
        "url": release.get("html_url", "https://github.com/michaelsouthward10-hue/N.E.M.O/releases"),
    }
