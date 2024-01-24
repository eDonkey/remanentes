# posts.py
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Depends
from sqlalchemy import Table, select, MetaData, Integer, String, Column
from databases import Database
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import NoCredentialsError
import logging
from typing import List
from users import get_current_user  # Import the get_current_user dependency

load_dotenv()

DATABASE_URL = os.getenv("PGSERVER")
database = Database(DATABASE_URL)
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

if not (AWS_ACCESS_KEY and AWS_SECRET_KEY and AWS_BUCKET_NAME):
    raise ValueError("AWS credentials or bucket name not provided.")

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

metadata = MetaData()

posts = Table(
    "posts",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("title", String, index=True),
    Column("description", String),
    Column("image", String),
    Column("current_price", Integer),
    Column("top_price", Integer),
    Column("creator_id", Integer, index=True),
)

router = APIRouter()

@router.on_event("startup")
async def startup_db_client():
    try:
        await database.connect()
        logging.info("Connected to the database")
    except Exception as e:
        logging.error(f"Error connecting to the database: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.on_event("shutdown")
async def shutdown_db_client():
    await database.disconnect()

@router.post("/posts/")
async def create_post(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    current_price: int = Form(...),
    top_price: int = Form(...),
    creator_id: int = Form(...),
    images: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),  # Use get_current_user directly in the route function
):
    # Process each uploaded image
    for image in images:
        contents = await image.read()  # Your logic to handle the file contents, such as uploading to S3

    # Use current_user as needed in your logic
    creator_id_from_token = current_user["sub"]

    # Your existing logic for creating a post
    post = {
        "title": title,
        "description": description,
        "current_price": current_price,
        "top_price": top_price,
        "creator_id": creator_id,
    }
    query = posts.insert().values(post)
    post_id = await database.execute(query)

    return {"message": "Post created"}

@router.get("/list_posts/", response_model=list[dict])
async def list_posts(skip: int = 0, limit: int = 10):
    query = select(posts).offset(skip).limit(limit)
    posts_list = await database.fetch_all(query)
    return [dict(post) for post in posts_list]
