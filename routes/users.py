from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas
from auth import get_current_user, require_admin

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
    db.delete(user)
    db.commit()
    return {"message": "Utilisateur supprimé"}
