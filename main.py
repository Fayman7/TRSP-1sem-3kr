from fastapi import Depends, FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html

from auth import auth_user, fake_users_db, pwd_context, verify_docs_credentials
from config import settings
from models import User, UserInDB

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.post("/register")
def register(user: User):
    hashed_password = pwd_context.hash(user.password)
    user_in_db = UserInDB(username=user.username, hashed_password=hashed_password)
    fake_users_db[user.username] = user_in_db
    return {"message": f"User '{user.username}' successfully registered"}


@app.get("/login")
def login(user: UserInDB = Depends(auth_user)):
    return {"message": f"Welcome, {user.username}!"}


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
