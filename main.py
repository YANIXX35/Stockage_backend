from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models

from routes import auth, files, folders, users, share

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="StorageApp API",
    description="Plateforme de stockage personnel — API REST",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://localhost:4201", "http://localhost:4202"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(users.router)
app.include_router(share.router)


@app.get("/")
def root():
    return {"message": "StorageApp API is running", "docs": "/docs"}
