from unittest.mock import patch

from flowstate.update_check import UpdateInfo, _is_newer, _parse_version, check_for_update


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
    with patch(
        "flowstate.update_check._fetch_latest_release",
        return_value=("v0.2.0", "https://github.com/Pelsynergy07/FlowState/releases/tag/v0.2.0"),
    ):
        result = check_for_update(cache_path=cache_path, current_version="0.1.4")

    assert result == UpdateInfo(version="0.2.0", url="https://github.com/Pelsynergy07/FlowState/releases/tag/v0.2.0")


def test_check_for_update_returns_none_when_already_current(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch(
        "flowstate.update_check._fetch_latest_release",
        return_value=("v0.1.4", "https://github.com/Pelsynergy07/FlowState/releases/tag/v0.1.4"),
    ):
        result = check_for_update(cache_path=cache_path, current_version="0.1.4")

    assert result is None


def test_check_for_update_returns_none_on_network_failure(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch("flowstate.update_check._fetch_latest_release", return_value=None):
        result = check_for_update(cache_path=cache_path, current_version="0.1.4")

    assert result is None


def test_check_for_update_uses_cache_within_interval(tmp_path):
    """Regression guard: a second check shortly after the first must not
    hit the network again -- it should reuse the cached result instead."""
    cache_path = tmp_path / "cache.json"
    with patch(
        "flowstate.update_check._fetch_latest_release",
        return_value=("v0.2.0", "https://github.com/Pelsynergy07/FlowState/releases/tag/v0.2.0"),
    ) as mock_fetch:
        first = check_for_update(cache_path=cache_path, current_version="0.1.4")
        second = check_for_update(cache_path=cache_path, current_version="0.1.4")

    assert mock_fetch.call_count == 1
    assert first == second == UpdateInfo(version="0.2.0", url="https://github.com/Pelsynergy07/FlowState/releases/tag/v0.2.0")


def test_check_for_update_force_bypasses_cache(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch(
        "flowstate.update_check._fetch_latest_release",
        return_value=("v0.2.0", "https://github.com/Pelsynergy07/FlowState/releases/tag/v0.2.0"),
    ) as mock_fetch:
        check_for_update(cache_path=cache_path, current_version="0.1.4")
        check_for_update(cache_path=cache_path, current_version="0.1.4", force=True)

    assert mock_fetch.call_count == 2
