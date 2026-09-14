from stickytasks.colors import Band, DEFAULT_BANDS
from stickytasks.config import DOCK_LEFT, DOCK_RIGHT, Settings


def test_defaults_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    Settings().save(path)
    loaded = Settings.load(path)
    assert loaded.panel_width == 380
    assert loaded.dock_edge == DOCK_RIGHT
    assert [b.label for b in loaded.bands] == [b.label for b in DEFAULT_BANDS]


def test_missing_file_yields_defaults(tmp_path):
    assert Settings.load(tmp_path / "nope.json").panel_width == 380


def test_corrupt_file_yields_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json at all")
    assert Settings.load(path).panel_width == 380


def test_non_object_json_yields_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[1, 2, 3]")
    assert Settings.load(path).panel_width == 380


def test_out_of_range_values_are_clamped(tmp_path):
    path = tmp_path / "settings.json"
    s = Settings()
    s.panel_width = 99999
    s.font_size = 400
    s.opacity = 5.0
    s.save(path)

    loaded = Settings.load(path)
    assert loaded.panel_width == 1200
    assert loaded.font_size == 24
    assert loaded.opacity == 1.0


def test_unknown_dock_edge_falls_back_to_right(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"dock_edge": "ceiling"}')
    assert Settings.load(path).dock_edge == DOCK_RIGHT


def test_left_edge_is_accepted(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"dock_edge": "left"}')
    assert Settings.load(path).dock_edge == DOCK_LEFT


def test_unknown_keys_survive_a_round_trip(tmp_path):
    """A settings file from a newer build must not be truncated by an older one."""
    import json

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"panel_width": 400, "some_future_option": {"a": 1}}))

    Settings.load(path).save(path)
    assert json.loads(path.read_text())["some_future_option"] == {"a": 1}


def test_band_list_without_a_catch_all_gains_one(tmp_path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"bands": [{"label": "Soon", "max_days": 2, "color": "#ff0000"}]}))

    bands = Settings.load(path).bands
    assert any(b.max_days is None for b in bands)


def test_malformed_band_entries_are_skipped(tmp_path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"bands": ["not a dict", {"label": "Ok", "max_days": 5, "color": "#00ff00"}]})
    )
    labels = [b.label for b in Settings.load(path).bands]
    assert "Ok" in labels


def test_empty_band_list_falls_back_to_defaults(tmp_path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"bands": []}))
    assert len(Settings.load(path).bands) == len(DEFAULT_BANDS)


def test_bad_colour_in_band_is_normalised(tmp_path):
    import json

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"bands": [{"label": "X", "max_days": None, "color": "not a colour"}]}))
    assert Settings.load(path).bands[0].color == "#9e9e9e"


def test_save_is_atomic_leaving_no_temp_file(tmp_path):
    path = tmp_path / "settings.json"
    Settings().save(path)
    assert [f.name for f in tmp_path.iterdir()] == ["settings.json"]


def test_bands_are_stored_sorted(tmp_path):
    import json

    path = tmp_path / "settings.json"
    s = Settings()
    s.bands = [Band("Later", None, "#00ff00"), Band("Soon", 1, "#ff0000")]
    s.save(path)
    stored = json.loads(path.read_text())["bands"]
    assert [b.label for b in Settings.load(path).bands] == ["Soon", "Later"]
    assert len(stored) == 2
