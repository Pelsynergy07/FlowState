from unittest.mock import patch

from flowstate.update_check import UpdateInfo, _ReleaseInfo, _is_newer, _parse_version, check_for_update

_RELEASE_URL = "https://github.com/Pelsynergy07/FlowState/releases/tag/v0.2.0"
_DOWNLOAD_URL = "https://github.com/Pelsynergy07/FlowState/releases/download/v0.2.0/FlowStateSetup.exe"


def test_parse_version_handles_v_prefix():
    assert _parse_version("v0.1.4") == (0, 1, 4)


def test_parse_version_handles_bare_version():
    assert _parse_version("0.1.4") == (0, 1, 4)


def test_parse_version_ignores_prerelease_suffix():
    assert _parse_version("v1.2.3-beta") == (1, 2, 3)


def test_parse_version_returns_none_for_garbage():
    assert _parse_version("not-a-version") is None


def test_is_newer_true_for_higher_patch():
    assert _is_newer("v0.1.5", "0.1.4") is True


def test_is_newer_false_for_equal_version():
    assert _is_newer("v0.1.4", "0.1.4") is False


def test_is_newer_false_for_older_version():
    assert _is_newer("v0.1.3", "0.1.4") is False


def test_is_newer_false_when_either_side_unparseable():
    assert _is_newer("garbage", "0.1.4") is False
    assert _is_newer("v0.1.5", "garbage") is False


def test_check_for_update_reports_newer_release(tmp_path):
    cache_path = tmp_path / "cache.json"
    release = _ReleaseInfo(tag="v0.2.0", html_url=_RELEASE_URL, download_url=_DOWNLOAD_URL, asset_size=123456)
    with patch("flowstate.update_check._fetch_latest_release", return_value=release):
        result = check_for_update(cache_path=cache_path, current_version="0.1.4")

    assert result == UpdateInfo(version="0.2.0", url=_RELEASE_URL, download_url=_DOWNLOAD_URL, asset_size=123456)


def test_check_for_update_returns_none_when_already_current(tmp_path):
    cache_path = tmp_path / "cache.json"
    release = _ReleaseInfo(tag="v0.1.4", html_url=_RELEASE_URL, download_url=_DOWNLOAD_URL, asset_size=123456)
    with patch("flowstate.update_check._fetch_latest_release", return_value=release):
        result = check_for_update(cache_path=cache_path, current_version="0.1.4")

    assert result is None


def test_check_for_update_returns_none_on_network_failure(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch("flowstate.update_check._fetch_latest_release", return_value=None):
        result = check_for_update(cache_path=cache_path, current_version="0.1.4")

    assert result is None


def test_check_for_update_handles_release_with_no_installer_asset(tmp_path):
    """A release published without the FlowStateSetup.exe asset attached
    (e.g. drafted but not yet uploaded) must still be reported as an
    available update -- just without a download_url, so the UI falls back
    to sending the user to the release page instead of offering one-click
    install."""
    cache_path = tmp_path / "cache.json"
    release = _ReleaseInfo(tag="v0.2.0", html_url=_RELEASE_URL, download_url=None, asset_size=None)
    with patch("flowstate.update_check._fetch_latest_release", return_value=release):
        result = check_for_update(cache_path=cache_path, current_version="0.1.4")

    assert result == UpdateInfo(version="0.2.0", url=_RELEASE_URL, download_url=None, asset_size=None)


def test_check_for_update_uses_cache_within_interval(tmp_path):
    """Regression guard: a second check shortly after the first must not
    hit the network again -- it should reuse the cached result instead."""
    cache_path = tmp_path / "cache.json"
    release = _ReleaseInfo(tag="v0.2.0", html_url=_RELEASE_URL, download_url=_DOWNLOAD_URL, asset_size=123456)
    with patch("flowstate.update_check._fetch_latest_release", return_value=release) as mock_fetch:
        first = check_for_update(cache_path=cache_path, current_version="0.1.4")
        second = check_for_update(cache_path=cache_path, current_version="0.1.4")

    assert mock_fetch.call_count == 1
    expected = UpdateInfo(version="0.2.0", url=_RELEASE_URL, download_url=_DOWNLOAD_URL, asset_size=123456)
    assert first == second == expected


def test_check_for_update_force_bypasses_cache(tmp_path):
    cache_path = tmp_path / "cache.json"
    release = _ReleaseInfo(tag="v0.2.0", html_url=_RELEASE_URL, download_url=_DOWNLOAD_URL, asset_size=123456)
    with patch("flowstate.update_check._fetch_latest_release", return_value=release) as mock_fetch:
        check_for_update(cache_path=cache_path, current_version="0.1.4")
        check_for_update(cache_path=cache_path, current_version="0.1.4", force=True)

    assert mock_fetch.call_count == 2
