from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas, auth as auth_utils
from auth import get_current_user, require_admin
import cloudinary_service

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=schemas.UserOut)
def get_profile(user: models.User = Depends(get_current_user)):
    return user


@router.get("", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    return db.query(models.User).all()


@router.put("/{user_id}/quota")
def update_quota(
    user_id: int,
    data: schemas.QuotaUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.quota_max = data.quota_max
    db.commit()
    return {"message": "Quota mis à jour"}


@router.put("/{user_id}/toggle-active")
def toggle_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_active = not user.is_active
    db.commit()
    return {"message": "Statut mis à jour", "is_active": user.is_active}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.is_admin:
        raise HTTPException(status_code=403, detail="Impossible de supprimer un admin")

    # 1. Récupérer les IDs des fichiers pour nettoyer les share_links
    files = db.query(models.File).filter(models.File.user_id == user_id).all()
    file_ids = [f.id for f in files]

    # 2. Supprimer les share_links pointant vers ces fichiers
    if file_ids:
        db.query(models.ShareLink).filter(
            models.ShareLink.file_id.in_(file_ids)
        ).delete(synchronize_session=False)

    # 3. Supprimer les fichiers de Cloudinary et de la DB
    for f in files:
        if f.nom_stockage:
            cloudinary_service.delete_file(f.nom_stockage, f.type_mime)
        db.delete(f)

    # 4. Supprimer les dossiers (nullifier d'abord les parent_id pour éviter la contrainte auto-référentielle)
    db.query(models.Folder).filter(models.Folder.user_id == user_id).update(
        {"parent_id": None}, synchronize_session=False
    )
    db.query(models.Folder).filter(models.Folder.user_id == user_id).delete(synchronize_session=False)

    # 5. Supprimer l'utilisateur
    db.delete(user)
    db.commit()
    return {"message": "Utilisateur supprimé"}


@router.post("", response_model=schemas.UserOut)
def create_user(
    data: schemas.UserCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    user = models.User(
        email=data.email,
        nom=data.nom,
        prenom=data.prenom,
        password_hash=auth_utils.hash_password(data.password),
        quota_max=data.quota_max,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=schemas.UserOut)
def update_user(
    user_id: int,
    data: schemas.UserUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if data.nom is not None: user.nom = data.nom
    if data.prenom is not None: user.prenom = data.prenom
    if data.email is not None: user.email = data.email
    if data.quota_max is not None: user.quota_max = data.quota_max
    if data.is_admin is not None: user.is_admin = data.is_admin
    db.commit()
    db.refresh(user)
    return user
