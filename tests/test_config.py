from openfieldday.config import Config, BONUS_CATALOG


def test_defaults():
    c = Config()
    assert c.n3fjp_host == "127.0.0.1"
    assert c.n3fjp_port == 1100
    assert c.power_multiplier == 2
    assert c.bonuses == {}
    assert c.bonus_points == 0


def test_bonus_points_sums_selected():
    c = Config(bonuses={"Emergency power": 100, "Public location": 100})
    assert c.bonus_points == 200


def test_bonus_catalog_is_nonempty_mapping():
    assert isinstance(BONUS_CATALOG, dict)
    assert "Emergency power" in BONUS_CATALOG
    assert all(isinstance(v, int) for v in BONUS_CATALOG.values())


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    original = Config(
        n3fjp_host="192.168.1.50", n3fjp_port=1100,
        power_multiplier=5, bonuses={"Emergency power": 100},
    )
    original.save(path)
    loaded = Config.load(path)
    assert loaded == original
    assert loaded.bonus_points == 100


def test_load_missing_file_returns_defaults(tmp_path):
    loaded = Config.load(tmp_path / "does_not_exist.yaml")
    assert loaded == Config()


def test_theme_overrides_default_empty_and_no_logo():
    c = Config()
    assert c.theme_color_overrides() == {"light": {}, "dark": {}}
    assert c.has_logo is False
    assert c.auto_light_start == 5 and c.auto_light_end == 21


def test_flat_colors_treated_as_dark_overrides():
    c = Config(colors={"accent": "#000000"})
    assert c.theme_color_overrides() == {"light": {}, "dark": {"accent": "#000000"}}


def test_nested_colors_kept_per_theme():
    c = Config(colors={"light": {"bg": "#ffffff"}, "dark": {"bg": "#000000"}})
    assert c.theme_color_overrides() == {"light": {"bg": "#ffffff"}, "dark": {"bg": "#000000"}}


def test_has_logo_tracks_file_existence(tmp_path):
    missing = Config(logo_path=str(tmp_path / "nope.png"))
    assert missing.has_logo is False
    f = tmp_path / "logo.png"
    f.write_bytes(b"x")
    assert Config(logo_path=str(f)).has_logo is True


def test_to_public_dict_exposes_overrides_and_hides_logo_path(tmp_path):
    f = tmp_path / "logo.png"
    f.write_bytes(b"x")
    pub = Config(logo_path=str(f), colors={"bg": "#111111"}).to_public_dict()
    assert "logo_path" not in pub
    assert pub["has_logo"] is True
    assert pub["colors"] == {"light": {}, "dark": {"bg": "#111111"}}
    assert pub["theme"] == {"auto_light_start": 5, "auto_light_end": 21}


def test_colors_logo_and_window_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    # Flat colors must still load (back-compat with the simple/legacy form).
    original = Config(colors={"accent": "#abcdef"}, logo_path="/srv/logo.png",
                      auto_light_start=6, auto_light_end=20)
    original.save(path)
    assert Config.load(path) == original


def test_nested_colors_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    original = Config(colors={"light": {"bg": "#fff"}, "dark": {"accent": "#000"}})
    original.save(path)
    assert Config.load(path) == original


def test_contest_window_parses_and_defaults_naive_to_utc():
    from datetime import datetime, timezone
    c = Config(contest_start="2026-06-27T18:00:00Z", contest_end="2026-06-28T21:00:00")
    start, end = c.contest_window()
    assert start == datetime(2026, 6, 27, 18, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 6, 28, 21, 0, tzinfo=timezone.utc)  # naive -> UTC
    assert Config().contest_window() == (None, None)


def test_contest_times_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    original = Config(contest_start="2026-06-27T18:00:00+00:00",
                      contest_end="2026-06-28T21:00:00+00:00")
    original.save(path)
    assert Config.load(path) == original
