Implement two functions in `services.py` to make the app work.

Phase 1 — understand the codebase: read `models.py` (data model), `utils.py` (helper), and `test_app.py` (expected behavior).

Phase 2 — implement:
1. `create_user(id, name, email)` — build a `User`, slugify `name` with the helper in `utils.py`, store the user in the module-level `USERS` list, and return it.
2. `list_users()` — return all users created so far.

Rules:
- Do not modify `test_app.py`, `models.py`, or `utils.py`.
- Run the tests with `python -m pytest -q test_app.py` to confirm.
