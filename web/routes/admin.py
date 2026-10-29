import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Form, status, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel

from web.database import get_db, User, Task, SystemSetting
from web.security import require_admin, hash_password
from web.task_manager import get_system_settings

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = ""
    role: Optional[str] = "teacher"


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    api_keys: List[str]
    model: Optional[str] = "gemini-2.5-flash"
    concurrent_workers: Optional[int] = 3


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard_page(
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    users_count = db.query(User).count()
    tasks_count = db.query(Task).count()
    completed_tasks = db.query(Task).filter(Task.status == "completed").count()

    sys_settings = get_system_settings()

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": admin,
            "users_count": users_count,
            "tasks_count": tasks_count,
            "completed_tasks": completed_tasks,
            "settings": sys_settings
        }
    )


@router.get("/api/admin/users")
async def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).order_by(User.id.asc()).all()
    res = []
    for u in users:
        task_count = db.query(Task).filter(Task.user_id == u.id).count()
        res.append({
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.strftime("%d/%m/%Y %H:%M") if u.created_at else "-",
            "last_login": u.last_login.strftime("%d/%m/%Y %H:%M") if u.last_login else "Chưa đăng nhập",
            "task_count": task_count
        })
    return {"users": res}


@router.post("/api/admin/users")
async def create_user(
    data: UserCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    clean_user = data.username.strip().lower()
    if not clean_user:
        raise HTTPException(status_code=400, detail="Tên đăng nhập không được để trống.")

    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu phải có ít nhất 6 ký tự.")

    existing = db.query(User).filter(User.username == clean_user).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tên đăng nhập này đã tồn tại.")

    role = data.role if data.role in ("admin", "teacher") else "teacher"

    new_user = User(
        username=clean_user,
        full_name=data.full_name or "",
        password_hash=hash_password(data.password),
        role=role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"success": True, "message": f"Đã tạo tài khoản {clean_user} thành công.", "user_id": new_user.id}


@router.put("/api/admin/users/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    # Không cho phép tự khóa tài khoản của chính mình
    if target.id == admin.id and data.is_active is False:
        raise HTTPException(status_code=400, detail="Bạn không thể tự khóa tài khoản quản trị của chính mình.")

    if data.full_name is not None:
        target.full_name = data.full_name
    if data.role is not None and data.role in ("admin", "teacher"):
        target.role = data.role
    if data.is_active is not None:
        target.is_active = data.is_active
    if data.new_password:
        if len(data.new_password) < 6:
            raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 6 ký tự.")
        target.password_hash = hash_password(data.new_password)

    db.commit()
    return {"success": True, "message": "Cập nhật tài khoản thành công."}


@router.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Không thể xóa tài khoản đang đăng nhập.")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")

    db.delete(target)
    db.commit()
    return {"success": True, "message": "Đã xóa tài khoản."}


@router.get("/api/admin/settings")
async def get_settings(admin: User = Depends(require_admin)):
    return get_system_settings()


@router.post("/api/admin/settings")
async def update_settings(
    data: SettingsUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Filter out empty or whitespace keys
    clean_keys = [k.strip() for k in data.api_keys if k and k.strip()]

    def set_db_setting(key: str, val_str: str):
        record = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not record:
            record = SystemSetting(key=key, value=val_str)
            db.add(record)
        else:
            record.value = val_str

    set_db_setting("api_keys", json.dumps(clean_keys))
    if data.model:
        set_db_setting("model", data.model)
    if data.concurrent_workers:
        set_db_setting("concurrent_workers", str(data.concurrent_workers))

    db.commit()
    return {"success": True, "message": "Đã lưu cài đặt hệ thống thành công."}


@router.get("/api/admin/history")
async def admin_history(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    tasks = db.query(Task).order_by(Task.created_at.desc()).limit(100).all()
    results = []
    for t in tasks:
        results.append({
            "id": t.id,
            "filename": t.original_filename,
            "user": t.user.full_name or t.user.username if t.user else "Đã xóa",
            "username": t.user.username if t.user else "-",
            "total_pages": t.total_pages,
            "status": t.status,
            "progress": t.progress,
            "created_at": t.created_at.strftime("%d/%m/%Y %H:%M") if t.created_at else "-",
            "completed_at": t.completed_at.strftime("%d/%m/%Y %H:%M") if t.completed_at else "-",
            "has_docx": bool(t.output_docx_path and os.path.exists(t.output_docx_path))
        })
    return {"history": results}
