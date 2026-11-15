from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import UserRegister, UserUpdate


def register_user(db: Session, data: UserRegister) -> User:
    email = str(data.email).strip().lower()
    user = User(
        full_name=data.full_name.strip(),
        email=email,
        hashed_password=hash_password(data.password),
        role="farmer",  # Le rôle est imposé par le backend, jamais par le client.
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette adresse email est déjà utilisée",
        )
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not user.is_active or user.role != "farmer":
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def update_user(db: Session, user: User, data: UserUpdate) -> User:
    if data.full_name is not None:
        cleaned_name = data.full_name.strip()
        if len(cleaned_name) < 2:
            raise HTTPException(status_code=422, detail="Le nom doit contenir au moins 2 caractères")
        user.full_name = cleaned_name
    db.commit()
    db.refresh(user)
    return user


def change_user_password(
    db: Session, user: User, old_password: str, new_password: str
) -> None:
    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect")
    if old_password == new_password:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit être différent")
    user.hashed_password = hash_password(new_password)
    db.commit()
