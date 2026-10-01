from models import User
from utils import slugify

USERS: list[User] = []


def create_user(id: int, name: str, email: str) -> User:
    # TODO: build a User with slugified name, store in USERS, return it.
    raise NotImplementedError


def list_users() -> list[User]:
    # TODO: return all users created so far.
    raise NotImplementedError
