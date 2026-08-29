import json

from flowstate.config import ConfigStore, FlowStateConfig, config_from_dict, config_to_dict


def test_default_config_has_expected_shape():
    cfg = FlowStateConfig()
    assert cfg.version == 1
    assert cfg.shortcuts.toggle == "ctrl+shift+space"
    assert cfg.capture.mode == "circle"
    assert cfg.model.asr_model_id == "large-v3-turbo"


def test_round_trip_through_disk(tmp_path):
    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    store.config.shortcuts.toggle = "ctrl+alt+d"
    store.config.capture.sensitivity = 0.8
    store.save()

    reloaded = ConfigStore(path=path)
    assert reloaded.config.shortcuts.toggle == "ctrl+alt+d"
    assert reloaded.config.capture.sensitivity == 0.8


def test_missing_fields_fall_back_to_defaults():
    # Simulates loading a config written by an older version that didn't
    # yet have the "cleanup" section.
    raw = {"version": 1, "shortcuts": {"toggle": "ctrl+space"}}
    cfg = config_from_dict(raw)
    assert cfg.shortcuts.toggle == "ctrl+space"
    assert cfg.shortcuts.push_to_talk == "alt_r"  # default filled in
    assert cfg.cleanup.grammar_enabled is True  # whole missing section defaulted


def test_corrupt_json_falls_back_to_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")
    store = ConfigStore(path=path)
    assert store.config == FlowStateConfig()


def test_save_notifies_subscribers(tmp_path):
    path = tmp_path / "config.json"
    store = ConfigStore(path=path)
    seen = []
    store.subscribe(lambda cfg: seen.append(cfg.capture.mode))

    store.config.capture.mode = "drag"
    store.save()

    assert seen == ["drag"]


def test_config_to_dict_is_json_serializable(tmp_path):
    cfg = FlowStateConfig()
    raw = config_to_dict(cfg)
    json.dumps(raw)  # must not raise
