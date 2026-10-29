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
        # 1. Khởi tạo tài khoản quản trị mặc định nếu chưa có
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

        # 2. Đảm bảo tài khoản as3 / 123123 luôn luôn tồn tại (không bao giờ bị mất khi khởi động lại server)
        as3_user = db.query(User).filter(User.username == "as3").first()
        if not as3_user:
            as3_user = User(
                username="as3",
                full_name="Giáo Viên AS3",
                password_hash=hash_password("123123"),
                role="teacher",
                is_active=True
            )
            db.add(as3_user)
            db.commit()

        # 3. Tự động nạp danh sách tài khoản cố định từ biến môi trường SEED_USERS (nếu có)
        # Cú pháp: SEED_USERS="gv1:matkhau1:teacher;gv2:matkhau2:teacher"
        seed_users_env = os.environ.get("SEED_USERS", "")
        if seed_users_env:
            for item in seed_users_env.split(";"):
                parts = item.strip().split(":")
                if len(parts) >= 2:
                    u_name = parts[0].strip().lower()
                    u_pass = parts[1].strip()
                    u_role = parts[2].strip() if len(parts) > 2 else "teacher"
                    exist_u = db.query(User).filter(User.username == u_name).first()
                    if not exist_u and u_name and len(u_pass) >= 6:
                        db.add(User(
                            username=u_name,
                            full_name=u_name.upper(),
                            password_hash=hash_password(u_pass),
                            role=u_role,
                            is_active=True
                        ))
            db.commit()
    finally:
        db.close()
