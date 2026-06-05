from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth as auth_utils

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=schemas.UserOut)
def register(data: schemas.UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    user = models.User(
        email=data.email,
        nom=data.nom,
        prenom=data.prenom,
        password_hash=auth_utils.hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not auth_utils.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte suspendu")
    token = auth_utils.create_access_token({"sub": str(user.id)})
    return {"access_token": token}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(auth_utils.get_current_user)):
    return current_user
