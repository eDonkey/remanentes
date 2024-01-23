import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
#from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Form
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from databases import Database
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('PGSERVER')
#DATABASE_URL = "postgresql://axelwdoviak:@localhost/axelwdoviak"
database = Database(DATABASE_URL)

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("name", String, index=True),
    Column("email", String, unique=True, index=True),
)

app = FastAPI()

# CORS middleware for handling Cross-Origin Resource Sharing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for simplicity. In production, you should restrict this.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates configuration
# templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_db_client():
    await database.connect()


@app.on_event("shutdown")
async def shutdown_db_client():
    await database.disconnect()

# @app.get("/", response_class=HTMLResponse)
# async def index(request: Request):
#     return templates.TemplateResponse("index.html", {"request": request})

# @app.get("/create_user", response_class=HTMLResponse)
# async def create_user_form(request: Request):
#     return templates.TemplateResponse("create_user.html", {"request": request})


@app.post("/users/", response_class=HTMLResponse)
async def create_user(request: Request, name: str = Form(...), email: str = Form(...)):
    user = {"name": name, "email": email}
    query = users.insert().values(user)
    user_id = await database.execute(query)
    return {"message": "User created"}
    #return templates.TemplateResponse("create_user_response.html", {"request": request, "user_id": user_id, "user": user})

@app.get("/users/{user_id}", response_model=dict)
async def read_user(user_id: int):
    query = users.select().where(users.c.id == user_id)
    user = await database.fetch_one(query)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)  # Convert the Record object to a dictionary


@app.get("/users/", response_model=list[dict])
async def read_users(skip: int = 0, limit: int = 10):
    query = users.select().offset(skip).limit(limit)
    users_list = await database.fetch_all(query)
    return [dict(user) for user in users_list]  # Convert each Record object to a dictionary


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
