import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Literal

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# --- Config ---

Role = Literal["admin", "user", "guest"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mode: Literal["DEV", "PROD"] = "DEV"
    docs_user: str = ""
    docs_password: str = ""
    jwt_secret: str = "your-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        normalized = str(value).upper()
        if normalized not in ("DEV", "PROD"):
            raise ValueError(f"Invalid MODE: {value!r}. Allowed values: DEV, PROD")
        return normalized


settings = Settings()

# --- Database ---

DATABASE_PATH = Path(__file__).parent / "app.db"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


# --- Models ---


class UserBase(BaseModel):
    username: str


class User(UserBase):
    password: str


class UserRegister(User):
    role: Role = "guest"


class UserInDB(UserBase):
    hashed_password: str
    role: Role = "guest"


class TokenUser(BaseModel):
    username: str
    role: Role


class ResourceCreate(BaseModel):
    name: str


class ResourceUpdate(BaseModel):
    name: str


class TodoCreate(BaseModel):
    title: str
    description: str


class TodoUpdate(BaseModel):
    title: str
    description: str
    completed: bool


class Todo(BaseModel):
    id: int
    title: str
    description: str
    completed: bool


# --- RBAC ---

ROLE_PERMISSIONS: dict[Role, set[str]] = {
    "admin": {"create", "read", "update", "delete"},
    "user": {"read", "update"},
    "guest": {"read"},
}


def has_permission(role: str, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role)  # type: ignore[arg-type]
    return permission in permissions if permissions else False


# --- Auth ---

security = HTTPBasic()
docs_security = HTTPBasic()
bearer_scheme = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

fake_users_db: dict[str, UserInDB] = {}
fake_resources_db: dict[int, dict] = {}
_next_resource_id = 1
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


def register_new_user(username: str, password: str, role: Role = "guest") -> None:
    if find_user(username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    fake_users_db[username] = UserInDB(
        username=username,
        hashed_password=pwd_context.hash(password),
        role=role,
    )


def authenticate_for_jwt(username: str, password: str) -> UserInDB:
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

    return user


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    username = payload.get("sub")
    role = payload.get("role")
    if username is None or role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    return TokenUser(username=username, role=role)


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(current_user: TokenUser = Depends(get_current_user)) -> TokenUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


def require_permission(permission: str) -> Callable:
    def dependency(current_user: TokenUser = Depends(get_current_user)) -> TokenUser:
        user = find_user(current_user.username)
        role = user.role if user is not None else current_user.role

        if not has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency


# --- Todo helpers ---


def _row_to_todo(row: sqlite3.Row) -> Todo:
    return Todo(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        completed=bool(row["completed"]),
    )


def _get_todo_row(conn: sqlite3.Connection, todo_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()


# --- App ---

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.state.limiter = limiter


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests"},
    )


@app.post("/register")
def register(user: User):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (user.username, user.password),
        )
        conn.commit()
        return {"message": "User registered successfully!"}
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )
    finally:
        conn.close()


@app.get("/login")
def basic_login(user: UserInDB = Depends(auth_user)):
    return {"message": f"Welcome, {user.username}!"}


@app.post("/login")
@limiter.limit("5/minute")
def jwt_login(request: Request, credentials: User):
    user = authenticate_for_jwt(credentials.username, credentials.password)
    access_token = create_access_token(user.username, user.role)
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/protected_resource")
def protected_resource(
    current_user: TokenUser = Depends(require_roles("admin", "user")),
):
    return {"message": "Access granted", "role": current_user.role}


@app.post("/admin/resource", status_code=status.HTTP_201_CREATED)
def admin_create_resource(
    resource: ResourceCreate,
    current_user: TokenUser = Depends(require_permission("create")),
):
    global _next_resource_id
    resource_id = _next_resource_id
    _next_resource_id += 1
    fake_resources_db[resource_id] = {"id": resource_id, "name": resource.name}
    return {"message": "Resource created", "resource": fake_resources_db[resource_id]}


@app.get("/resources")
def read_resources(
    current_user: TokenUser = Depends(require_permission("read")),
):
    return {"resources": list(fake_resources_db.values())}


@app.put("/resources/{resource_id}")
def update_resource(
    resource_id: int,
    resource: ResourceUpdate,
    current_user: TokenUser = Depends(require_permission("update")),
):
    if resource_id not in fake_resources_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    fake_resources_db[resource_id]["name"] = resource.name
    return {"message": "Resource updated", "resource": fake_resources_db[resource_id]}


@app.delete("/resources/{resource_id}")
def delete_resource(
    resource_id: int,
    current_user: TokenUser = Depends(require_permission("delete")),
):
    if resource_id not in fake_resources_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    deleted = fake_resources_db.pop(resource_id)
    return {"message": "Resource deleted", "resource": deleted}


@app.post("/todos", status_code=status.HTTP_201_CREATED, response_model=Todo)
def create_todo(todo: TodoCreate):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO todos (title, description, completed) VALUES (?, ?, 0)",
            (todo.title, todo.description),
        )
        conn.commit()
        row = _get_todo_row(conn, cursor.lastrowid)
        return _row_to_todo(row)
    finally:
        conn.close()


@app.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: int):
    conn = get_db_connection()
    try:
        row = _get_todo_row(conn, todo_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Todo not found",
            )
        return _row_to_todo(row)
    finally:
        conn.close()


@app.put("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, todo: TodoUpdate):
    conn = get_db_connection()
    try:
        row = _get_todo_row(conn, todo_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Todo not found",
            )

        conn.execute(
            "UPDATE todos SET title = ?, description = ?, completed = ? WHERE id = ?",
            (todo.title, todo.description, int(todo.completed), todo_id),
        )
        conn.commit()
        updated_row = _get_todo_row(conn, todo_id)
        return _row_to_todo(updated_row)
    finally:
        conn.close()


@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):
    conn = get_db_connection()
    try:
        row = _get_todo_row(conn, todo_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Todo not found",
            )

        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
        return {"message": "Todo deleted successfully"}
    finally:
        conn.close()


async def docs_not_found():
    raise HTTPException(status_code=404, detail="Not Found")


if settings.mode == "DEV":

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui(_: str = Depends(verify_docs_credentials)):
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - Swagger UI",
        )

    @app.get("/openapi.json", include_in_schema=False)
    async def custom_openapi(_: str = Depends(verify_docs_credentials)):
        return app.openapi()

    @app.get("/redoc", include_in_schema=False)
    async def redoc_hidden():
        raise HTTPException(status_code=404, detail="Not Found")

else:
    for path in ("/docs", "/openapi.json", "/redoc"):
        app.add_api_route(
            path,
            docs_not_found,
            methods=["GET"],
            include_in_schema=False,
        )
