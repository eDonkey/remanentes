# users.py
import os
import jwt
from jwt.exceptions import ExpiredSignatureError
from jwt import ExpiredSignatureError
from fastapi import APIRouter, HTTPException, Request, Form, Depends, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from sqlalchemy import Table, Column, Integer, String, MetaData, select
from databases import Database
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

router = APIRouter()

metadata = MetaData()

DATABASE_URL = os.getenv('PGSERVER')
#database = Database(DATABASE_URL)
database = Database(DATABASE_URL, min_size=1, max_size=20)

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

async def startup_db_client():
    await database.connect()

async def shutdown_db_client():
    await database.disconnect()

async def authenticate_user(email: str, password: str):
    query = select([users.c.email, users.c.password]).where(users.c.email == email)
    user = await database.fetch_one(query)
    if user and password_hashing.verify(password, user['password']):
        return user
    return None

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

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_data = {"sub": user["email"]}
    access_token = create_jwt_token(token_data)
    return {"access_token": access_token, "token_type": "bearer"}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_token(token: str):
    try:
        # Decode the token using the secret key
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        # Return the decoded payload
        return payload
    except jwt.ExpiredSignatureError:
        # Token has expired
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        # Invalid token
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        user = verify_token(token)
        return user
    except HTTPException as e:
        # Catch the HTTPException raised by verify_token and return it
        raise e

# def get_current_user(token: str = Depends(oauth2_scheme)):
#     user = verify_token(token)
#     if user is None:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
#     return user
