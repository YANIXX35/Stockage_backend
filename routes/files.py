import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
import models, schemas
from auth import get_current_user
import cloudinary_service

router = APIRouter(prefix="/api/files", tags=["Files"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _local_path(user_id: int, nom_stockage: str) -> str:
    return os.path.join(UPLOAD_DIR, str(user_id), nom_stockage)


@router.post("/upload", response_model=List[schemas.FileOut])
async def upload_files(
    files: List[UploadFile] = FastAPIFile(...),
    folder_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    if folder_id:
        folder = db.query(models.Folder).filter(
            models.Folder.id == folder_id,
            models.Folder.user_id == user.id
        ).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Dossier introuvable")

    # Vérification quota
    total_size = 0
    contents = []
    for file in files:
        content = await file.read()
        total_size += len(content)
        contents.append(content)

    if user.quota_used + total_size > user.quota_max:
        raise HTTPException(status_code=400, detail="Quota de stockage dépassé")

    uploaded = []
    for file, content in zip(files, contents):
        mime = file.content_type or "application/octet-stream"
        ext = os.path.splitext(file.filename or "")[1]
        public_id = f"storage/{user.id}/{uuid.uuid4().hex}"
        nom_stockage = f"{uuid.uuid4().hex}{ext}"

        # Upload vers Cloudinary
        cloudinary_url = cloudinary_service.upload_file(content, public_id, mime)

        db_file = models.File(
            nom_original=file.filename or nom_stockage,
            nom_stockage=public_id,       # stocke le public_id Cloudinary
            type_mime=mime,
            taille=len(content),
            user_id=user.id,
            folder_id=folder_id,
            cloudinary_url=cloudinary_url,
        )
        db.add(db_file)
        user.quota_used += len(content)
        uploaded.append(db_file)

    db.commit()
    for f in uploaded:
        db.refresh(f)
    return uploaded


@router.get("", response_model=List[schemas.FileOut])
def list_files(
    folder_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    return db.query(models.File).filter(
        models.File.user_id == user.id,
        models.File.folder_id == folder_id,
        models.File.is_deleted == False
    ).all()


@router.get("/trash", response_model=List[schemas.FileOut])
def list_trash(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    return db.query(models.File).filter(
        models.File.user_id == user.id,
        models.File.is_deleted == True
    ).all()


@router.get("/{file_id}/download")
def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.user_id == user.id,
        models.File.is_deleted == False
    ).first()
    if not file:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    # Cloudinary (nouveaux fichiers)
    if file.cloudinary_url:
        return RedirectResponse(url=file.cloudinary_url, status_code=302)

    # Fallback disque local (anciens fichiers)
    path = _local_path(user.id, file.nom_stockage)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le disque")
    return FileResponse(path=path, filename=file.nom_original, media_type=file.type_mime)


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    permanent: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.user_id == user.id
    ).first()
    if not file:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    if permanent:
        # Supprimer de Cloudinary
        if file.cloudinary_url:
            cloudinary_service.delete_file(file.nom_stockage, file.type_mime)
        else:
            # Fallback disque local
            path = _local_path(user.id, file.nom_stockage)
            if os.path.exists(path):
                os.remove(path)
        user.quota_used = max(0, user.quota_used - file.taille)
        db.delete(file)
    else:
        file.is_deleted = True
        file.deleted_at = datetime.utcnow()

    db.commit()
    return {"message": "Fichier supprimé"}


@router.put("/{file_id}/restore", response_model=schemas.FileOut)
def restore_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.user_id == user.id,
        models.File.is_deleted == True
    ).first()
    if not file:
        raise HTTPException(status_code=404, detail="Fichier introuvable dans la corbeille")
    file.is_deleted = False
    file.deleted_at = None
    db.commit()
    db.refresh(file)
    return file


@router.post("/{file_id}/share", response_model=schemas.ShareOut)
def share_file(
    file_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    file = db.query(models.File).filter(
        models.File.id == file_id,
        models.File.user_id == user.id,
        models.File.is_deleted == False
    ).first()
    if not file:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    share = models.ShareLink(
        token=uuid.uuid4().hex,
        file_id=file_id,
        created_by=user.id
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share
