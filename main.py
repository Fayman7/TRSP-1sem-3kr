import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from auth import auth_user, authenticate_for_jwt, verify_docs_credentials
from config import settings
from database import get_db_connection
from jwt_auth import create_access_token, get_current_user, require_permission, require_roles
from models import ResourceCreate, ResourceUpdate, TokenUser, User, UserInDB

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.state.limiter = limiter

fake_resources_db: dict[int, dict] = {}
_next_resource_id = 1


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
