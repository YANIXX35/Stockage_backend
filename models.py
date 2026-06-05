from sqlalchemy import Column, Integer, String, Boolean, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    quota_max = Column(BigInteger, default=2 * 1024 * 1024 * 1024)  # 2 Go
    quota_used = Column(BigInteger, default=0)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    files = relationship("File", back_populates="owner", foreign_keys="File.user_id")
    folders = relationship("Folder", back_populates="owner")


class Folder(Base):
    __tablename__ = "folders"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="folders")
    files = relationship("File", back_populates="folder")
    parent = relationship("Folder", remote_side="Folder.id", foreign_keys=[parent_id], back_populates="children")
    children = relationship("Folder", foreign_keys=[parent_id], back_populates="parent")


class File(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True, index=True)
    nom_original = Column(String, nullable=False)
    nom_stockage = Column(String, nullable=False, unique=True)
    type_mime = Column(String, default="application/octet-stream")
    taille = Column(BigInteger, default=0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="files", foreign_keys=[user_id])
    folder = relationship("Folder", back_populates="files")


class ShareLink(Base):
    __tablename__ = "share_links"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    file = relationship("File")
