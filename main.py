# main.py
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from databases import Database
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta



load_dotenv()

ENABLE_POSTS_MODULE = os.getenv("ENABLE_POSTS_MODULE", "False").lower() == "true"
ENABLE_USERS_MODULE = os.getenv("ENABLE_USERS_MODULE", "False").lower() == "true"
ENABLE_BIDS_MODULE = os.getenv("ENABLE_BIDS_MODULE", "False").lower() == "true"

app = FastAPI()

if ENABLE_POSTS_MODULE:
    from posts import (
        router as posts_router,
        startup_db_client as posts_startup,
        shutdown_db_client as posts_shutdown
    )
    app.include_router(posts_router, prefix="/posts", tags=["posts"])
if ENABLE_USERS_MODULE:
    from users import (
        router as users_router,
        startup_db_client as user_startup,
        shutdown_db_client as user_shutdown,
        authenticate_user as authenticate_user
    )
    app.include_router(users_router, prefix="/users", tags=["users"])  # Include the user router
if ENABLE_BIDS_MODULE:  # Assuming you have a variable ENABLE_BIDS_MODULE set to True
    from bids import (
       router as bids_router,
        startup_db_client as bids_startup,
        shutdown_db_client as bids_shutdown
    )
    app.include_router(bids_router, prefix="/bids", tags=["bids"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
DATABASE_URL = os.getenv('PGSERVER')
#database = Database(DATABASE_URL)
database = Database(DATABASE_URL, min_size=1, max_size=20)

origins = [
    "http://pegaso.us",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing configuration
password_hashing = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer is a class for creating a dependency to get the token from the request headers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_jwt_token(data: dict) -> str:
    """Create a JWT token."""
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str) -> dict:
    """Verify the JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Set the expiration time for the token (e.g., 3 days)
    expires_in = timedelta(days=3)

    # Calculate the expiration datetime
    expiration_datetime = datetime.utcnow() + expires_in

    # token_data includes the subject and expiration time
    token_data = {
        "sub": (await user)["email"],
        "exp": expiration_datetime,
    }

    # Create a JWT token
    access_token = create_jwt_token(token_data)

    # Return the response with the access token and expires_in
    return {"access_token": access_token, "token_type": "bearer", "expires_in": expires_in.total_seconds()}

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = verify_jwt_token(token)
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Fetch the user from the database based on the email
    query = users.select().where(users.c.email == email)
    user = await database.fetch_one(query)
    if user is None:
        raise credentials_exception

    return user

@app.get("/version", response_model=dict)
async def read_build_version():
    try:
        with open("Build.Version", "r") as file:
            version_line = file.readline().strip()
            return {"version": version_line}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Build.Version file not found")

@app.on_event("startup")
async def startup_db_client():
    if ENABLE_USERS_MODULE:
        await user_startup()
    if ENABLE_POSTS_MODULE:
        await posts_startup()
    if ENABLE_BIDS_MODULE:
        await bids_startup()
    await database.connect()

@app.on_event("shutdown")
async def shutdown_db_client():
    if ENABLE_BIDS_MODULE:
        await bids_shutdown
    if ENABLE_USERS_MODULE:
        await user_shutdown()
    if ENABLE_POSTS_MODULE:
        await posts_shutdown()
    await database.disconnect()

