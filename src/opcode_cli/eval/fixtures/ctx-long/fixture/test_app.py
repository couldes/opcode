import app
import config
import data


def test_render_colors():
    for feature, key in config.FEATURES.items():
        assert app.render_color(feature) == data.LOOKUP[key]
