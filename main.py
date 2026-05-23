from fastapi import Depends, FastAPI

from auth import auth_user, fake_users_db, pwd_context
from models import User, UserInDB

app = FastAPI()


@app.post("/register")
def register(user: User):
    hashed_password = pwd_context.hash(user.password)
    user_in_db = UserInDB(username=user.username, hashed_password=hashed_password)
    fake_users_db[user.username] = user_in_db
    return {"message": f"User '{user.username}' successfully registered"}


@app.get("/login")
def login(user: UserInDB = Depends(auth_user)):
    return {"message": f"Welcome, {user.username}!"}
