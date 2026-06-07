from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ── AUTH ──────────────────────────────────────────────────
class OtpRequest(BaseModel):
    email: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

class UserRegister(BaseModel):
    email: str
    nom: str
    prenom: str
    password: str
    otp: str


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    nom: str
    prenom: str
    quota_max: int
    quota_used: int
    is_admin: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── FOLDERS ───────────────────────────────────────────────
class FolderCreate(BaseModel):
    nom: str
    parent_id: Optional[int] = None


class FolderRename(BaseModel):
    nom: str


class FolderOut(BaseModel):
    id: int
    nom: str
    parent_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ── FILES ─────────────────────────────────────────────────
class FileRegister(BaseModel):
    nom_original: str
    type_mime: str
    taille: int
    cloudinary_url: str
    public_id: str
    folder_id: Optional[int] = None


class FileOut(BaseModel):
    id: int
    nom_original: str
    type_mime: str
    taille: int
    folder_id: Optional[int]
    cloudinary_url: Optional[str] = None
    is_deleted: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── SHARE ─────────────────────────────────────────────────
class ShareOut(BaseModel):
    token: str
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── ADMIN ─────────────────────────────────────────────────
class QuotaUpdate(BaseModel):
    quota_max: int

class UserCreate(BaseModel):
    email: str
    nom: str
    prenom: str
    password: str
    quota_max: int = 2 * 1024 * 1024 * 1024

class UserUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    email: Optional[str] = None
    quota_max: Optional[int] = None
    is_admin: Optional[bool] = None
