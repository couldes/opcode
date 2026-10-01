import yaml

import feature


def test_matches_current_config():
    with open("config.yml", encoding="utf-8") as f:
        current = yaml.safe_load(f)["feature"]
    expected = "enabled" if current == "new" else "disabled"
    assert feature.label() == expected
