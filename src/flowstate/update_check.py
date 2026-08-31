"""Checks GitHub Releases for a newer FlowState build than the one running.

Deliberately dependency-free (stdlib urllib, not requests) and Qt-free, so
it can run on a background thread and be unit tested without a QApplication.
Never raises into the caller and never blocks longer than the timeout below
-- no internet, a GitHub outage, or an unparseable tag all just mean "no
update to report this run," not a crash or a stalled UI.

Results are cached under the app data dir so a normal launch doesn't hit
GitHub's API every time; real network checks happen at most once per
CHECK_INTERVAL_SECONDS unless force=True.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__, paths

logger = logging.getLogger("flowstate.update_check")

GITHUB_REPO = "Pelsynergy07/FlowState"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT_SECONDS = 5
CHECK_INTERVAL_SECONDS = 6 * 60 * 60  # don't re-hit the API more than every 6h


@dataclass(frozen=True)
class UpdateInfo:
    version: str  # e.g. "0.1.5", no leading "v"
    url: str  # release page to send the user to


def _parse_version(tag: str) -> tuple[int, int, int] | None:
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", tag.strip())
    if not match:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _is_newer(candidate_tag: str, current_version: str) -> bool:
    candidate = _parse_version(candidate_tag)
    current = _parse_version(current_version)
    if candidate is None or current is None:
        return False
    return candidate > current


def _cache_path(cache_path: Path | None) -> Path:
    return cache_path or (paths.app_data_dir() / "update_check_cache.json")


def _load_cache(cache_path: Path) -> dict:
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache_path: Path, data: dict) -> None:
    try:
        cache_path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        logger.debug("Could not write update-check cache", exc_info=True)


def _fetch_latest_release() -> tuple[str, str] | None:
    """Returns (tag_name, html_url) for the latest GitHub release, or None
    on any network/parse failure."""
    request = urllib.request.Request(
        GITHUB_API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "FlowState-UpdateCheck"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        logger.debug("Update check request failed", exc_info=True)
        return None
    tag = data.get("tag_name")
    url = data.get("html_url")
    if not tag or not url:
        return None
    return tag, url


def check_for_update(
    force: bool = False,
    cache_path: Path | None = None,
    current_version: str = __version__,
) -> UpdateInfo | None:
    """Best-effort check for a release newer than current_version.

    Safe to call from any thread. Returns None whenever there's nothing
    newer to report -- including every failure mode -- so callers never
    need to distinguish "checked, no update" from "couldn't check."
    """
    resolved_cache_path = _cache_path(cache_path)
    cache = _load_cache(resolved_cache_path)
    now = time.time()

    if not force and now - cache.get("checked_at", 0) < CHECK_INTERVAL_SECONDS:
        tag = cache.get("latest_tag")
        url = cache.get("latest_url")
        if tag and url and _is_newer(tag, current_version):
            return UpdateInfo(version=tag.lstrip("vV"), url=url)
        return None

    result = _fetch_latest_release()
    if result is None:
        return None
    tag, url = result
    _save_cache(resolved_cache_path, {"checked_at": now, "latest_tag": tag, "latest_url": url})

    if _is_newer(tag, current_version):
        return UpdateInfo(version=tag.lstrip("vV"), url=url)
    return None
