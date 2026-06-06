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
