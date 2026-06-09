import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from database import engine, Base, SessionLocal
import models

logger = logging.getLogger(__name__)

from routes import auth, files, folders, users, share
import cloudinary_service
from config import ADMIN_EMAIL, ADMIN_QUOTA

Base.metadata.create_all(bind=engine)


def _promote_first_admin():
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(
            models.User.email.ilike(ADMIN_EMAIL)
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
    _secret = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_USE_A_LONG_RANDOM_STRING")
    if _secret == "CHANGE_ME_IN_PRODUCTION_USE_A_LONG_RANDOM_STRING":
        logger.warning("⚠️  SECRET_KEY non définie — configurez-la dans les variables d'env Render !")

    # Ajout de la colonne cloudinary_url si elle n'existe pas encore
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE files ADD COLUMN IF NOT EXISTS cloudinary_url VARCHAR"
        ))
        conn.commit()
    _promote_first_admin()
    cloudinary_service.ensure_upload_preset()


@app.get("/")
def root():
    return {"message": "StorageApp API is running", "docs": "/docs"}


@app.get("/health")
def health():
    """Endpoint de santé ultra-léger — aucune requête SQL, sert uniquement au warmup Render."""
    return {"status": "ok"}
