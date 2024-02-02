from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Table, select, MetaData, Integer, String, Column, insert, update, and_
from databases import Database
from dotenv import load_dotenv
import os
from users import get_current_user
from posts import posts
import logging

load_dotenv()

DATABASE_URL = os.getenv("PGSERVER")
database = Database(DATABASE_URL, min_size=1, max_size=20)
router = APIRouter()
metadata = MetaData()

bids = Table(
    "bids",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("user_id", Integer, index=True),
    Column("post_id", Integer, index=True),
    Column("bid_amount", Integer),
)

@router.on_event("startup")
async def startup_db_client():
    try:
        await database.connect()
        logging.info("Connected to the database")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")
@router.on_event("shutdown")
async def shutdown_db_client():
    await database.disconnect()
@router.post("/place_bid/{post_id}")
async def place_bid(
    post_id: int,
    bid_amount: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["id"]
    query_post = select(posts).where(posts.c.id == post_id)
    existing_post = await database.fetch_one(query_post)
    if not existing_post:
        raise HTTPException(status_code=404, detail="Post not found")
    if bid_amount <= existing_post["current_price"]:
        raise HTTPException(status_code=400, detail="Bid amount must be greater than the current price")
    new_current_price = bid_amount
    query_update_post = update(posts).where(posts.c.id == post_id).values(current_price=new_current_price)
    await database.execute(query_update_post)
    query_insert_bid = insert(bids).values(user_id=user_id, post_id=post_id, bid_amount=bid_amount)
    bid_id = await database.execute(query_insert_bid)
    return {"message": "Bid placed successfully", "bid_id": bid_id}