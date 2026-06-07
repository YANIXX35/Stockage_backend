import os
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models, schemas, auth as auth_utils

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# In-memory OTP stores
_otp_store: dict[str, dict] = {}        # pour l'inscription
_reset_store: dict[str, dict] = {}      # pour la réinitialisation du mot de passe


def _smtp_send(to_email: str, subject: str, html: str) -> None:
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_email or not smtp_password:
        raise RuntimeError("SMTP non configuré")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_email
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP("smtp.gmail.com", 587) as srv:
        srv.starttls()
        srv.login(smtp_email, smtp_password)
        srv.sendmail(smtp_email, to_email, msg.as_string())


def _send_otp_email(to_email: str, code: str) -> None:
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:420px;margin:0 auto;padding:24px;">
      <h2 style="color:#6C63FF;margin-bottom:4px;">StorageApp</h2>
      <p style="color:#555;">Voici votre code de vérification pour créer votre compte :</p>
      <div style="font-size:2.2rem;font-weight:700;letter-spacing:12px;color:#6C63FF;
                  padding:20px;background:#f4f3ff;text-align:center;border-radius:10px;
                  margin:20px 0;">{code}</div>
      <p style="color:#888;font-size:0.85rem;">Ce code expire dans <strong>10 minutes</strong>.
         Ne le partagez avec personne.</p>
    </div>
    """
    _smtp_send(to_email, "Votre code de vérification — StorageApp", html)


def _send_reset_email(to_email: str, code: str) -> None:
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:420px;margin:0 auto;padding:24px;">
      <h2 style="color:#6C63FF;margin-bottom:4px;">StorageApp</h2>
      <p style="color:#555;">Vous avez demandé la réinitialisation de votre mot de passe.</p>
      <div style="font-size:2.2rem;font-weight:700;letter-spacing:12px;color:#6C63FF;
                  padding:20px;background:#f4f3ff;text-align:center;border-radius:10px;
                  margin:20px 0;">{code}</div>
      <p style="color:#888;font-size:0.85rem;">Ce code expire dans <strong>10 minutes</strong>.
         Si vous n'avez pas fait cette demande, ignorez cet email.</p>
    </div>
    """
    _smtp_send(to_email, "Réinitialisation de mot de passe — StorageApp", html)


@router.post("/send-otp")
def send_otp(data: schemas.OtpRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    code = str(random.randint(100000, 999999))
    _otp_store[data.email] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
    }

    background_tasks.add_task(_send_otp_email, data.email, code)

    return {"message": "Code envoyé"}


@router.post("/register", response_model=schemas.UserOut)
def register(data: schemas.UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    stored = _otp_store.get(data.email)
    if not stored:
        raise HTTPException(status_code=400, detail="Code OTP introuvable. Demandez un nouveau code.")
    if stored["expires_at"] < datetime.utcnow():
        _otp_store.pop(data.email, None)
        raise HTTPException(status_code=400, detail="Code OTP expiré. Demandez un nouveau code.")
    if stored["code"] != data.otp:
        raise HTTPException(status_code=400, detail="Code OTP incorrect")

    _otp_store.pop(data.email, None)

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


@router.post("/forgot-password")
def forgot_password(data: schemas.ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        return {"message": "Si cet email est enregistré, un code a été envoyé"}

    code = str(random.randint(100000, 999999))
    _reset_store[data.email] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
    }

    background_tasks.add_task(_send_reset_email, data.email, code)

    return {"message": "Code envoyé"}


@router.post("/reset-password")
def reset_password(data: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    stored = _reset_store.get(data.email)
    if not stored:
        raise HTTPException(status_code=400, detail="Code OTP introuvable. Demandez un nouveau code.")
    if stored["expires_at"] < datetime.utcnow():
        _reset_store.pop(data.email, None)
        raise HTTPException(status_code=400, detail="Code OTP expiré. Demandez un nouveau code.")
    if stored["code"] != data.otp:
        raise HTTPException(status_code=400, detail="Code OTP incorrect")

    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    _reset_store.pop(data.email, None)
    user.password_hash = auth_utils.hash_password(data.new_password)
    db.commit()

    return {"message": "Mot de passe réinitialisé avec succès"}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(auth_utils.get_current_user)):
    return current_user
