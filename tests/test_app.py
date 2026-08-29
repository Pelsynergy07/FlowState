from flowstate.app import RecordingController


def test_nearest_segment_text_picks_enclosing_segment():
    segments = [
        (0.0, 2.0, "hello there"),
        (2.0, 5.0, "look at this bug"),
        (5.0, 8.0, "and here is the fix"),
    ]
    assert RecordingController._nearest_segment_text(segments, 3.5) == "look at this bug"


def test_nearest_segment_text_picks_closest_when_between_segments():
    segments = [
        (0.0, 1.0, "first"),
        (4.0, 5.0, "second"),
    ]
    # 1.4 is closer to the end of the first segment (0.4 away) than the
    # start of the second (2.6 away).
    assert RecordingController._nearest_segment_text(segments, 1.4) == "first"


def test_nearest_segment_text_handles_no_segments():
    assert RecordingController._nearest_segment_text([], 3.0) == ""
