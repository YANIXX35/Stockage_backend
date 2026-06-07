import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine, Base, SessionLocal
import models

from routes import auth, files, folders, users, share

Base.metadata.create_all(bind=engine)

ADMIN_QUOTA = 100 * 1024 * 1024 * 1024  # 100 Go

def _promote_first_admin():
    email = os.getenv("FIRST_ADMIN_EMAIL", "").strip().lower()
    if not email:
        return
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(
            models.User.email.ilike(email)
        ).first()
        if user:
            changed = False
            if not user.is_admin:
                user.is_admin = True
                changed = True
            if user.quota_max < ADMIN_QUOTA:
                user.quota_max = ADMIN_QUOTA
                changed = True
            if changed:
                db.commit()
    finally:
        db.close()

app = FastAPI(
    title="StorageApp API",
    description="Plateforme de stockage personnel — API REST",
    version="1.0.0"
)

_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
if _origins_env.strip() == "*":
    ALLOWED_ORIGINS = ["*"]
    ALLOW_CREDENTIALS = False
else:
    ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",")]
    ALLOW_CREDENTIALS = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(users.router)
app.include_router(share.router)


@app.on_event("startup")
def on_startup():
    # Ajout de la colonne cloudinary_url si elle n'existe pas encore
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE files ADD COLUMN IF NOT EXISTS cloudinary_url VARCHAR"
        ))
        conn.commit()
    _promote_first_admin()


@app.get("/")
def root():
    return {"message": "StorageApp API is running", "docs": "/docs"}
