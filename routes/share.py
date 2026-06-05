import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
import models

router = APIRouter(prefix="/api/share", tags=["Share"])


@router.get("/{token}/download")
def download_shared(token: str, db: Session = Depends(get_db)):
    link = db.query(models.ShareLink).filter(models.ShareLink.token == token).first()
    if not link:
        raise HTTPException(status_code=404, detail="Lien invalide")
    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Lien expiré")

    file = db.query(models.File).filter(
        models.File.id == link.file_id,
        models.File.is_deleted == False
    ).first()
    if not file:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    path = os.path.join("uploads", str(file.user_id), file.nom_stockage)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fichier physique introuvable")

    return FileResponse(path=path, filename=file.nom_original, media_type=file.type_mime)


@router.get("/{token}/info")
def shared_file_info(token: str, db: Session = Depends(get_db)):
    link = db.query(models.ShareLink).filter(models.ShareLink.token == token).first()
    if not link:
        raise HTTPException(status_code=404, detail="Lien invalide")
    if link.expires_at and link.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Lien expiré")

    file = db.query(models.File).filter(
        models.File.id == link.file_id,
        models.File.is_deleted == False
    ).first()
    if not file:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    return {
        "nom": file.nom_original,
        "type_mime": file.type_mime,
        "taille": file.taille,
        "created_at": file.created_at
    }
