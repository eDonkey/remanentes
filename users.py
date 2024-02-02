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
DATABASE_URL = os.getenv('PGSERVER')

router = APIRouter()
metadata = MetaData()
database = Database(DATABASE_URL, min_size=1, max_size=20)

def bversion():
    try:
        with open("Build.Version", "r") as file:
            version_line = file.readline().strip()
            return version_line
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Build.Version file not found")

versionn = bversion()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("name", String, index=True),
    Column("email", String, unique=True, index=True),
    Column("password", String),
    Column("created_on_version", String),
)

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
    hashed_password = password_hashing.hash(password)
    user = {"name": name, "email": email, "password": hashed_password, "created_on_version": versionn}
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
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = verify_token(token)
        user_email: str = payload.get("sub")
        if user_email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    try:
        query = users.select().where(users.c.email == user_email)
        user = await database.fetch_one(query)
        if user is None:
            raise credentials_exception
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user: {str(e)}")
    return user