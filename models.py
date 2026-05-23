from typing import Literal

from pydantic import BaseModel


class UserBase(BaseModel):
    username: str


class User(UserBase):
    password: str


class UserRegister(User):
    role: Literal["admin", "user", "guest"] = "guest"


class UserInDB(UserBase):
    hashed_password: str
    role: Literal["admin", "user", "guest"] = "guest"


class TokenUser(BaseModel):
    username: str
    role: Literal["admin", "user", "guest"]


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
