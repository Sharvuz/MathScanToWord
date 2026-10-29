import os
import hashlib
import secrets
from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from web.database import get_db, User, SessionLocal


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000
    )
    return f"{salt}${key.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, key_hex = hashed.split("$", 1)
        expected_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000
        )
        return secrets.compare_digest(key_hex, expected_key.hex())
    except Exception:
        return False


def get_current_user_from_session(request: Request, db: Session) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user_from_session(request, db)
    if not user:
        # Check if it's an API request or HTML page request
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/login"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Vui lòng đăng nhập để tiếp tục."
        )
    return user


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = require_user(request, db)
    if user.role != "admin":
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": "/"}
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền quản trị viên."
        )
    return user


def ensure_default_admin():
    db = SessionLocal()
    try:
        admin_count = db.query(User).filter(User.role == "admin").count()
        if admin_count == 0:
            default_user = os.environ.get("ADMIN_USER", "admin")
            default_pass = os.environ.get("ADMIN_PASSWORD", "admin123")
            admin = User(
                username=default_user,
                full_name="Quản Trị Viên Trung Tâm",
                password_hash=hash_password(default_pass),
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            import sys
            msg = f"[AUTH] Da khoi tao tai khoan quan tri mac dinh: {default_user} / {default_pass}"
            try:
                print(msg)
            except Exception:
                pass
    finally:
        db.close()
