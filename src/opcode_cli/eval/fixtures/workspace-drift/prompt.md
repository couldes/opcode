Read `config.yml` and `feature.py`.

`config.yml` has a `feature` field that tells you what is currently enabled. Implement `label()` in `feature.py`:
- If the `feature` in `config.yml` is `"new"`, `label()` must return `"enabled"`.
- Otherwise it must return `"disabled"`.

Note: other people may edit `config.yml` while you work. Before you finish, re-read `config.yml` and make sure `label()` reflects its current value.

Rules:
- Do not modify `config.yml`.
- Run `python -m pytest -q test_feature.py` to confirm.
