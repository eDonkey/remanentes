# main.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from databases import Database
from dotenv import load_dotenv

load_dotenv()

ENABLE_POSTS_MODULE = os.getenv("ENABLE_POSTS_MODULE", "False").lower() == "true"
ENABLE_USERS_MODULE = os.getenv("ENABLE_USERS_MODULE", "False").lower() == "true"

if ENABLE_POSTS_MODULE:
    from posts import router as posts_router

if ENABLE_USERS_MODULE:
    from users import router as users_router

DATABASE_URL = os.getenv('PGSERVER')
database = Database(DATABASE_URL)

app = FastAPI()

# CORS middleware for handling Cross-Origin Resource Sharing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_db_client():
    await database.connect()

@app.on_event("shutdown")
async def shutdown_db_client():
    await database.disconnect()

app.include_router(posts_router, prefix="/posts", tags=["posts"])
app.include_router(users_router, prefix="/users", tags=["users"])  # Include the user router