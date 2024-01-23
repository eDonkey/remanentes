import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Form
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from databases import Database
from dotenv import load_dotenv
from passlib.context import CryptContext  # Import CryptContext for password hashing

load_dotenv()

ENABLE_POSTS_MODULE = os.getenv("ENABLE_POSTS_MODULE", "False").lower() == "true"

if ENABLE_POSTS_MODULE:
    from posts import router as posts_router

DATABASE_URL = os.getenv('PGSERVER')
database = Database(DATABASE_URL)

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("name", String, index=True),
    Column("email", String, unique=True, index=True),
    Column("password", String),  # Add a new column for storing hashed passwords
)

app = FastAPI()

# CORS middleware for handling Cross-Origin Resource Sharing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing configuration
password_hashing = CryptContext(schemes=["bcrypt"], deprecated="auto")


@app.on_event("startup")
async def startup_db_client():
    await database.connect()


@app.on_event("shutdown")
async def shutdown_db_client():
    await database.disconnect()

app.include_router(posts_router, prefix="/posts", tags=["posts"])


@app.post("/users/")
async def create_user(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...)):
    # Hash the password before storing it
    hashed_password = password_hashing.hash(password)
    user = {"name": name, "email": email, "password": hashed_password}
    query = users.insert().values(user)
    user_id = await database.execute(query)
    return {"message": "User created", "user_id": user_id}


@app.get("/users/{user_id}", response_model=dict)
async def read_user(user_id: int):
    query = users.select().where(users.c.id == user_id)
    user = await database.fetch_one(query)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)


@app.get("/users/", response_model=list[dict])
async def read_users(skip: int = 0, limit: int = 10):
    query = users.select().offset(skip).limit(limit)
    users_list = await database.fetch_all(query)
    return [dict(user) for user in users_list]


@app.put("/users/{user_id}", response_model=dict)
async def update_user(user_id: int, user: dict):
    query = users.update().where(users.c.id == user_id).values(user)
    await database.execute(query)
    return {"id": user_id, **user}


@app.delete("/users/{user_id}", response_model=dict)
async def delete_user(user_id: int):
    query = users.delete().where(users.c.id == user_id)
    await database.execute(query)
    return {"message": "User deleted"}