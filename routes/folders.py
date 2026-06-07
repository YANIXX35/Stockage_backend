from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models, schemas
from auth import get_current_user
import cloudinary_service

router = APIRouter(prefix="/api/folders", tags=["Folders"])


def _delete_folder_cascade(folder_id: int, user_id: int, db: Session) -> int:
    """Supprime récursivement un dossier et tout son contenu. Retourne le quota libéré."""
    freed = 0
    files = db.query(models.File).filter(
        models.File.folder_id == folder_id,
        models.File.user_id == user_id
    ).all()
    for f in files:
        # Supprimer les share_links liés
        db.query(models.ShareLink).filter(models.ShareLink.file_id == f.id).delete(synchronize_session=False)
        if f.nom_stockage:
            cloudinary_service.delete_file(f.nom_stockage, f.type_mime)
        freed += f.taille
        db.delete(f)

    sub_folders = db.query(models.Folder).filter(
        models.Folder.parent_id == folder_id
    ).all()
    for sub in sub_folders:
        freed += _delete_folder_cascade(sub.id, user_id, db)
        db.delete(sub)

    return freed


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
    freed = _delete_folder_cascade(folder_id, user.id, db)
    db.delete(folder)
    user.quota_used = max(0, user.quota_used - freed)
    db.commit()
    return {"message": "Dossier supprimé"}
