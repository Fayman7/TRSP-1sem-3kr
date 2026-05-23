from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from auth import (
    auth_user,
    authenticate_for_jwt,
    register_new_user,
    verify_docs_credentials,
)
from config import settings
from jwt_auth import create_access_token, get_current_user
from models import User, UserInDB

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests"},
    )


@app.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("1/minute")
def register(request: Request, user: User):
    register_new_user(user.username, user.password)
    return {"message": "New user created"}


@app.get("/login")
def basic_login(user: UserInDB = Depends(auth_user)):
    return {"message": f"Welcome, {user.username}!"}


@app.post("/login")
@limiter.limit("5/minute")
def jwt_login(request: Request, credentials: User):
    username = authenticate_for_jwt(credentials.username, credentials.password)
    access_token = create_access_token(username)
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/protected_resource")
def protected_resource(_: str = Depends(get_current_user)):
    return {"message": "Access granted"}


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
