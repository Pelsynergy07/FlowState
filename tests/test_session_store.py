from datetime import datetime, timedelta

import pytest

from flowstate.session import store


@pytest.fixture
def sessions_root(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(store.paths, "sessions_dir", lambda: root)
    return root


def _make_session_folder(root, when: datetime, size_bytes: int = 0, suffix: str = "aaaaaa"):
    name = f"{when.strftime('%Y%m%d-%H%M%S')}-{suffix}"
    folder = root / name
    folder.mkdir()
    if size_bytes:
        (folder / "audio.wav").write_bytes(b"0" * size_bytes)
    return folder


def test_create_and_save_session_writes_files(sessions_root):
    session = store.create_session(source_app="Notepad")
    session.transcript = "Hello world."
    store.save_session(session)

    assert session.transcript_path.read_text(encoding="utf-8") == "Hello world."
    assert "Hello world." in session.context_md_path.read_text(encoding="utf-8")
    assert "Notepad" in session.context_md_path.read_text(encoding="utf-8")


def test_list_sessions_is_newest_first(sessions_root):
    now = datetime.now()
    old = _make_session_folder(sessions_root, now - timedelta(days=1), suffix="aaaaaa")
    new = _make_session_folder(sessions_root, now, suffix="bbbbbb")

    result = store.list_sessions()
    assert result[0] == new
    assert result[1] == old


def test_retention_deletes_sessions_older_than_7_days(sessions_root):
    now = datetime.now()
    ancient = _make_session_folder(sessions_root, now - timedelta(days=10), suffix="aaaaaa")
    recent = _make_session_folder(sessions_root, now - timedelta(days=1), suffix="bbbbbb")

    deleted = store.enforce_retention(now=now)

    assert ancient in deleted
    assert not ancient.exists()
    assert recent.exists()


def test_retention_evicts_oldest_when_over_size_cap(sessions_root):
    now = datetime.now()
    # Three sessions, each 200 MB, all within the 7-day window: total 600 MB
    # exceeds the 500 MB cap, so the oldest must be evicted first.
    oldest = _make_session_folder(sessions_root, now - timedelta(hours=3), size_bytes=200 * 1024 * 1024, suffix="aaaaaa")
    middle = _make_session_folder(sessions_root, now - timedelta(hours=2), size_bytes=200 * 1024 * 1024, suffix="bbbbbb")
    newest = _make_session_folder(sessions_root, now - timedelta(hours=1), size_bytes=200 * 1024 * 1024, suffix="cccccc")

    deleted = store.enforce_retention(now=now)

    assert oldest in deleted
    assert not oldest.exists()
    assert middle.exists()
    assert newest.exists()


def test_retention_keeps_everything_under_the_caps(sessions_root):
    now = datetime.now()
    a = _make_session_folder(sessions_root, now - timedelta(hours=1), size_bytes=1024, suffix="aaaaaa")
    b = _make_session_folder(sessions_root, now - timedelta(hours=2), size_bytes=1024, suffix="bbbbbb")

    deleted = store.enforce_retention(now=now)

    assert deleted == []
    assert a.exists()
    assert b.exists()
