import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from passlib.context import CryptContext

from config import settings
from models import UserInDB

security = HTTPBasic()
docs_security = HTTPBasic()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

fake_users_db: dict[str, UserInDB] = {}
_dummy_hash = pwd_context.hash("dummy_password")


def find_user(username: str) -> UserInDB | None:
    for stored_username, user in fake_users_db.items():
        if secrets.compare_digest(username, stored_username):
            return user
    return None


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Basic"},
    )


def verify_docs_credentials(
    credentials: HTTPBasicCredentials = Depends(docs_security),
) -> str:
    correct_user = secrets.compare_digest(credentials.username, settings.docs_user)
    correct_password = secrets.compare_digest(credentials.password, settings.docs_password)
    if correct_user and correct_password:
        return credentials.username

    secrets.compare_digest(credentials.username, "dummy_user")
    secrets.compare_digest(credentials.password, "dummy_password")
    raise unauthorized()


def auth_user(credentials: HTTPBasicCredentials = Depends(security)) -> UserInDB:
    user = fake_users_db.get(credentials.username)

    if user is not None:
        correct_username = secrets.compare_digest(credentials.username, user.username)
        correct_password = pwd_context.verify(credentials.password, user.hashed_password)
        if correct_username and correct_password:
            return user

    pwd_context.verify(credentials.password, _dummy_hash)
    raise unauthorized()


def register_new_user(username: str, password: str) -> None:
    if find_user(username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    hashed_password = pwd_context.hash(password)
    fake_users_db[username] = UserInDB(username=username, hashed_password=hashed_password)


def authenticate_for_jwt(username: str, password: str) -> str:
    user = find_user(username)

    if user is None:
        pwd_context.verify(password, _dummy_hash)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not secrets.compare_digest(username, user.username):
        pwd_context.verify(password, _dummy_hash)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not pwd_context.verify(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization failed",
        )

    return user.username
