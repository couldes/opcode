Implement `render_color(feature)` in `app.py` so the app returns the correct color for each feature.

How it works:
- `data.py` holds a large `LOOKUP` map from color key (e.g. `"col-0001"`) to hex value (e.g. `"#000001"`).
- `config.py` maps each feature name to a color key.
- `render_color(feature)` must first resolve the feature name through the config, then resolve the resulting key through `LOOKUP`, and return the hex string.

Rules:
- Do not modify `data.py`, `config.py`, or any test file.
- You will need to read `data.py` (it is large) and `config.py` to find the right keys.
- Run `python -m pytest -q test_app.py` to confirm your implementation.
