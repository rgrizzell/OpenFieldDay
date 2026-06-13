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


def test_default_colors_and_no_logo():
    c = Config()
    assert c.merged_colors["accent"] == "#ffd166"
    assert c.has_logo is False


def test_color_overrides_merge_onto_defaults():
    c = Config(colors={"accent": "#000000"})
    m = c.merged_colors
    assert m["accent"] == "#000000"     # overridden
    assert m["bg"] == "#0b1021"         # untouched default still present


def test_has_logo_tracks_file_existence(tmp_path):
    missing = Config(logo_path=str(tmp_path / "nope.png"))
    assert missing.has_logo is False
    f = tmp_path / "logo.png"
    f.write_bytes(b"x")
    assert Config(logo_path=str(f)).has_logo is True


def test_to_public_dict_exposes_colors_and_hides_logo_path(tmp_path):
    f = tmp_path / "logo.png"
    f.write_bytes(b"x")
    pub = Config(logo_path=str(f), colors={"bg": "#111111"}).to_public_dict()
    assert "logo_path" not in pub
    assert pub["has_logo"] is True
    assert pub["colors"]["bg"] == "#111111"


def test_colors_and_logo_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    original = Config(colors={"accent": "#abcdef"}, logo_path="/srv/logo.png")
    original.save(path)
    assert Config.load(path) == original
