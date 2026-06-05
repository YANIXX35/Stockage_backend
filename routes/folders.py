from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models, schemas
from auth import get_current_user

router = APIRouter(prefix="/api/folders", tags=["Folders"])


@router.post("", response_model=schemas.FolderOut)
def create_folder(
    data: schemas.FolderCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    if data.parent_id:
        parent = db.query(models.Folder).filter(
            models.Folder.id == data.parent_id,
            models.Folder.user_id == user.id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Dossier parent introuvable")

    folder = models.Folder(nom=data.nom, user_id=user.id, parent_id=data.parent_id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.get("", response_model=List[schemas.FolderOut])
def list_folders(
    parent_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    return db.query(models.Folder).filter(
        models.Folder.user_id == user.id,
        models.Folder.parent_id == parent_id
    ).all()


@router.get("/{folder_id}", response_model=schemas.FolderOut)
def get_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    folder = db.query(models.Folder).filter(
        models.Folder.id == folder_id,
        models.Folder.user_id == user.id
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    return folder


@router.put("/{folder_id}", response_model=schemas.FolderOut)
def rename_folder(
    folder_id: int,
    data: schemas.FolderRename,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    folder = db.query(models.Folder).filter(
        models.Folder.id == folder_id,
        models.Folder.user_id == user.id
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    folder.nom = data.nom
    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    folder = db.query(models.Folder).filter(
        models.Folder.id == folder_id,
        models.Folder.user_id == user.id
    ).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    db.delete(folder)
    db.commit()
    return {"message": "Dossier supprimé"}
