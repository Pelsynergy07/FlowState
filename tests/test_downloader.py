import time

from flowstate.asr.downloader import download_dir_with_progress


def test_progress_reaches_100_and_download_runs_once(tmp_path):
    calls = []
    target = tmp_path / "model"

    def fake_download():
        calls.append(1)
        target.mkdir(parents=True, exist_ok=True)
        (target / "weights.bin").write_bytes(b"x" * 1024)

    progress_values = []
    download_dir_with_progress(
        target,
        expected_bytes=1024,
        do_download=fake_download,
        on_progress=progress_values.append,
    )

    assert calls == [1]
    assert progress_values[-1] == 100


def test_progress_is_capped_at_99_until_the_final_explicit_call(tmp_path):
    """Never claim "done" from the polling estimate alone -- only the
    explicit post-download emit should ever report 100, since the
    estimate is based on an approximate expected size and can overshoot
    (e.g. the actual download turns out larger than approx_size_mb)."""
    target = tmp_path / "model"
    target.mkdir()
    # Already twice the "expected" size before do_download even runs, so
    # the poll thread's estimate would be >100% if it weren't capped.
    (target / "weights.bin").write_bytes(b"x" * 2048)

    def slow_download():
        time.sleep(0.6)  # let the poll thread get at least one iteration in

    progress_values = []
    download_dir_with_progress(
        target,
        expected_bytes=1024,
        do_download=slow_download,
        on_progress=progress_values.append,
    )

    assert progress_values[:-1], "expected at least one poll before the final emit"
    assert all(v <= 99 for v in progress_values[:-1])
    assert progress_values[-1] == 100


def test_target_dir_is_created_if_missing(tmp_path):
    target = tmp_path / "nested" / "model"
    download_dir_with_progress(target, expected_bytes=100, do_download=lambda: None)
    assert target.is_dir()


def test_works_without_a_progress_callback(tmp_path):
    target = tmp_path / "model"
    # Must not raise just because on_progress was omitted.
    download_dir_with_progress(target, expected_bytes=100, do_download=lambda: None)
