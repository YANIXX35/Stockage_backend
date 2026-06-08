import logging
import random
import re
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models, schemas, auth as auth_utils
from config import ADMIN_EMAIL, ADMIN_QUOTA

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# In-memory OTP stores (clés toujours en minuscules)
_otp_store: dict[str, dict] = {}
_reset_store: dict[str, dict] = {}

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$')


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


def _smtp_send(to_email: str, subject: str, html: str) -> None:
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    if not smtp_email or not smtp_password:
        logger.error("SMTP non configuré — SMTP_EMAIL ou SMTP_PASSWORD manquant")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_email
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as srv:
            srv.starttls()
            srv.login(smtp_email, smtp_password)
            srv.sendmail(smtp_email, to_email, msg.as_string())
        logger.info("Email envoyé à %s", to_email)
    except Exception as exc:
        logger.error("Échec envoi email à %s : %s", to_email, exc)


def _send_otp_email(to_email: str, code: str) -> None:
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:420px;margin:0 auto;padding:24px;">
      <h2 style="color:#6C63FF;margin-bottom:4px;">Eglise URD — StorageApp</h2>
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
      <h2 style="color:#6C63FF;margin-bottom:4px;">Eglise URD — StorageApp</h2>
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
    email = data.email.strip().lower()
    if not _valid_email(email):
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    code = str(random.randint(100000, 999999))
    _otp_store[email] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
    }
    background_tasks.add_task(_send_otp_email, email, code)
    return {"message": "Code envoyé"}


@router.post("/register", response_model=schemas.UserOut)
def register(data: schemas.UserRegister, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    stored = _otp_store.get(email)
    if not stored:
        raise HTTPException(status_code=400, detail="Code OTP introuvable. Demandez un nouveau code.")
    if stored["expires_at"] < datetime.utcnow():
        _otp_store.pop(email, None)
        raise HTTPException(status_code=400, detail="Code OTP expiré. Demandez un nouveau code.")
    if stored["code"] != data.otp:
        raise HTTPException(status_code=400, detail="Code OTP incorrect")

    _otp_store.pop(email, None)

    user = models.User(
        email=email,
        nom=data.nom.strip(),
        prenom=data.prenom.strip(),
        password_hash=auth_utils.hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = db.query(models.User).filter(models.User.email.ilike(email)).first()
    if not user or not auth_utils.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte suspendu")

    if user.email.strip().lower() == ADMIN_EMAIL:
        changed = False
        if not user.is_admin:
            user.is_admin = True
            changed = True
        if user.quota_max < ADMIN_QUOTA:
            user.quota_max = ADMIN_QUOTA
            changed = True
        if changed:
            db.commit()

    token = auth_utils.create_access_token({"sub": str(user.id)})
    return {"access_token": token}


@router.post("/forgot-password")
def forgot_password(data: schemas.ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if not _valid_email(email):
        raise HTTPException(status_code=400, detail="Adresse email invalide")
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = db.query(models.User).filter(models.User.email.ilike(email)).first()
    if not user:
        return {"message": "Si cet email est enregistré, un code a été envoyé"}

    code = str(random.randint(100000, 999999))
    _reset_store[email] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
    }
    background_tasks.add_task(_send_reset_email, user.email, code)
    return {"message": "Code envoyé"}


@router.post("/reset-password")
def reset_password(data: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    stored = _reset_store.get(email)
    if not stored:
        raise HTTPException(status_code=400, detail="Code OTP introuvable. Demandez un nouveau code.")
    if stored["expires_at"] < datetime.utcnow():
        _reset_store.pop(email, None)
        raise HTTPException(status_code=400, detail="Code OTP expiré. Demandez un nouveau code.")
    if stored["code"] != data.otp:
        raise HTTPException(status_code=400, detail="Code OTP incorrect")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = db.query(models.User).filter(models.User.email.ilike(email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    _reset_store.pop(email, None)
    user.password_hash = auth_utils.hash_password(data.new_password)
    if user.email != email:
        user.email = email
    db.commit()

    return {"message": "Mot de passe réinitialisé avec succès"}


@router.put("/change-password")
def change_password(
    data: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    if not auth_utils.verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit faire au moins 6 caractères")
    current_user.password_hash = auth_utils.hash_password(data.new_password)
    db.commit()
    return {"message": "Mot de passe modifié avec succès"}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(auth_utils.get_current_user)):
    return current_user
