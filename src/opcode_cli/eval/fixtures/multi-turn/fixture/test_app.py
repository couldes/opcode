from services import create_user, list_users


def test_create_and_list():
    create_user(1, "Alice Smith", "alice@example.com")
    create_user(2, "Bob Jones", "bob@example.com")
    users = list_users()
    assert len(users) == 2
    assert users[0].id == 1
    assert users[0].name == "alice-smith"
    assert users[0].email == "alice@example.com"
    assert users[1].id == 2
    assert users[1].name == "bob-jones"
    assert users[1].email == "bob@example.com"
