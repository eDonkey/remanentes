# posts.py
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from sqlalchemy import Table, Column, Integer, String, MetaData
from databases import Database
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("PGSERVER")
database = Database(DATABASE_URL)

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
    await database.connect()


@router.on_event("shutdown")
async def shutdown_db_client():
    await database.disconnect()


@router.post("/posts/", response_class=HTMLResponse)
async def create_post(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    image: str = Form(...),
    current_price: int = Form(...),
    top_price: int = Form(...),
    creator_id: int = Form(...),
):
    post = {
        "title": title,
        "description": description,
        "image": image,
        "current_price": current_price,
        "top_price": top_price,
        "creator_id": creator_id,
    }
    query = posts.insert().values(post)
    post_id = await database.execute(query)
    return {"message": "Post created"}


@router.get("/posts/{post_id}", response_model=dict)
async def read_post(post_id: int):
    query = posts.select().where(posts.c.id == post_id)
    post = await database.fetch_one(query)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return dict(post)


@router.get("/posts/", response_model=list[dict])
async def read_posts(skip: int = 0, limit: int = 10):
    query = posts.select().offset(skip).limit(limit)
    posts_list = await database.fetch_all(query)
    return [dict(post) for post in posts_list]


@router.put("/posts/{post_id}", response_model=dict)
async def update_post(post_id: int, post: dict):
    query = posts.update().where(posts.c.id == post_id).values(post)
    await database.execute(query)
    return {"id": post_id, **post}


@router.delete("/posts/{post_id}", response_model=dict)
async def delete_post(post_id: int):
    query = posts.delete().where(posts.c.id == post_id)
    await database.execute(query)
    return {"message": "Post deleted"}
