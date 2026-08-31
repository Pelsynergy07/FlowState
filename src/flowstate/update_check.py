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
INSTALLER_ASSET_NAME = "FlowStateSetup.exe"  # matches installer.iss's OutputBaseFilename
REQUEST_TIMEOUT_SECONDS = 5
CHECK_INTERVAL_SECONDS = 6 * 60 * 60  # don't re-hit the API more than every 6h


@dataclass(frozen=True)
class UpdateInfo:
    version: str  # e.g. "0.1.5", no leading "v"
    url: str  # release page to send the user to
    download_url: str | None = None  # direct link to the installer asset, if attached
    asset_size: int | None = None  # bytes, as reported by GitHub


@dataclass(frozen=True)
class _ReleaseInfo:
    tag: str
    html_url: str
    download_url: str | None
    asset_size: int | None


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


def _find_installer_asset(assets: list) -> tuple[str | None, int | None]:
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") == INSTALLER_ASSET_NAME:
            return asset.get("browser_download_url"), asset.get("size")
    return None, None


def _fetch_latest_release() -> _ReleaseInfo | None:
    """Returns the latest GitHub release's tag, page URL, and (if attached)
    the installer asset's direct download URL/size -- or None on any
    network/parse failure."""
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
    html_url = data.get("html_url")
    if not tag or not html_url:
        return None
    download_url, asset_size = _find_installer_asset(data.get("assets") or [])
    return _ReleaseInfo(tag=tag, html_url=html_url, download_url=download_url, asset_size=asset_size)


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
            return UpdateInfo(
                version=tag.lstrip("vV"),
                url=url,
                download_url=cache.get("download_url"),
                asset_size=cache.get("asset_size"),
            )
        return None

    result = _fetch_latest_release()
    if result is None:
        return None
    _save_cache(
        resolved_cache_path,
        {
            "checked_at": now,
            "latest_tag": result.tag,
            "latest_url": result.html_url,
            "download_url": result.download_url,
            "asset_size": result.asset_size,
        },
    )

    if _is_newer(result.tag, current_version):
        return UpdateInfo(
            version=result.tag.lstrip("vV"),
            url=result.html_url,
            download_url=result.download_url,
            asset_size=result.asset_size,
        )
    return None
