# user.py
from fastapi import APIRouter, HTTPException, Request, Form
from sqlalchemy import Table, Column, Integer, String, MetaData
from databases import Database
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from passlib.context import CryptContext

router = APIRouter()

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("name", String, index=True),
    Column("email", String, unique=True, index=True),
    Column("password", String),
)

# Password hashing configuration
password_hashing = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/users/")
async def create_user(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    # Hash the password before storing it
    hashed_password = password_hashing.hash(password)
    user = {"name": name, "email": email, "password": hashed_password}
    query = users.insert().values(user)
    user_id = await database.execute(query)
    return {"message": "User created", "user_id": user_id}


@router.get("/users/{user_id}", response_model=dict)
async def read_user(user_id: int):
    query = users.select().where(users.c.id == user_id)
    user = await database.fetch_one(query)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)


@router.get("/users/", response_model=list[dict])
async def read_users(skip: int = 0, limit: int = 10):
    query = users.select().offset(skip).limit(limit)
    users_list = await database.fetch_all(query)
    return [dict(user) for user in users_list]


@router.put("/users/{user_id}", response_model=dict)
async def update_user(user_id: int, user: dict):
    query = users.update().where(users.c.id == user_id).values(user)
    await database.execute(query)
    return {"id": user_id, **user}


@router.delete("/users/{user_id}", response_model=dict)
async def delete_user(user_id: int):
    query = users.delete().where(users.c.id == user_id)
    await database.execute(query)
    return {"message": "User deleted"}
