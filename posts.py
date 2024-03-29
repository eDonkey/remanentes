# posts.py
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Depends, Path, Query
from sqlalchemy import Table, select, MetaData, Integer, String, Column, DateTime, func
from databases import Database
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import NoCredentialsError
import logging
from typing import List
from users import get_current_user

load_dotenv()

DATABASE_URL = os.getenv("PGSERVER")
database = Database(DATABASE_URL, min_size=1, max_size=20)
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

if not (AWS_ACCESS_KEY and AWS_SECRET_KEY and AWS_BUCKET_NAME):
    raise ValueError("AWS credentials or bucket name not provided.")

s3 = boto3.client(
    "s3",
    region_name='sfo3',
    endpoint_url='https://stg-remanentes.sfo3.digitaloceanspaces.com',
    aws_access_key_id=os.getenv('SPACES_KEY'),
    aws_secret_access_key=os.getenv('SPACES_SECRET')
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
    Column("created_at", DateTime),
    Column("expire_date", DateTime),
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
@router.post("/create")
async def create_post(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    current_price: int = Form(...),
    top_price: int = Form(...),
    creator_id: int = Form(...),
    images: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    creator_id_from_token = current_user["sub"]
    post = {
        "title": title,
        "description": description,
        "current_price": current_price,
        "top_price": top_price,
        "creator_id": creator_id,
    }
    query = posts.insert().values(post)
    post_id = await database.execute(query)
    image_filenames = []
    for image in images:
        contents = await image.read()
        directory = f"images/{post_id}"
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(directory, image.filename)
        with open(file_path, "wb") as file:
            file.write(contents)
        try:
            s3.upload_file(
                file_path,
                AWS_BUCKET_NAME,
                f"images/{post_id}/{image.filename}",
                ExtraArgs={"ACL": "public-read"},
            )
        except NoCredentialsError:
            raise HTTPException(
                status_code=500, detail="AWS credentials not available"
            )
        finally:
            os.remove(file_path)
            image_filenames.append(f"{image.filename}")
    image_filenames_str = ",".join(image_filenames)
    update_query = posts.update().where(posts.c.id == post_id).values(image=image_filenames_str)
    await database.execute(update_query)
    return {"message": "Post created"}

@router.get("/list", response_model=List[dict])
async def list_posts(skip: int = 0, limit: int = 10):
    try:
        total_query = select(func.count()).select_from(posts)
        total_posts = await database.fetch_val(total_query)
        
        if total_posts is None or total_posts == 0:
            return [{"message": "No hay subastas activas en este momento."}]
        else:
            query = select(posts).offset(skip).limit(limit)
            posts_list = await database.fetch_all(query)
            return [dict(post) for post in posts_list]
    except Exception as e:
        print(f"Error: {e}")
        return {"message": "An error occurred while fetching posts."}

@router.get("/details/{post_id}", response_model=dict)
async def get_post_details(post_id: int = Path(..., title="The ID of the post to retrieve")):
    query = select(posts).where(posts.c.id == post_id)
    post_details = await database.fetch_one(query)
    if post_details is None:
        raise HTTPException(status_code=404, detail="Post not found")

    return dict(post_details)
@router.get("/search", response_model=List[dict])
async def search_posts(
    query_string: str = Query(..., title="Search query"),
    skip: int = Query(0, title="Number of items to skip"),
    limit: int = Query(10, title="Number of items to retrieve")
):
    # Use ILIKE to perform case-insensitive search in PostgreSQL
    search_query = f"%{query_string}%"

    search_condition = (
        (posts.c.title.ilike(search_query)) | 
        (posts.c.description.ilike(search_query))
    )

    query = select(posts).where(search_condition).offset(skip).limit(limit)
    search_results = await database.fetch_all(query)

    return [dict(post) for post in search_results]