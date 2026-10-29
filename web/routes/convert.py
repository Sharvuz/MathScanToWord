import os
import uuid
import json
from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel

from web.database import get_db, User, Task
from web.security import require_user, get_current_user_from_session
from web.config import UPLOADS_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB
from web.task_manager import submit_task, cancel_task

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


class TaskStartRequest(BaseModel):
    compact_paper_saver: bool = True
    ai_geometry_redraw: bool = True
    auto_detect_columns: bool = True
    enhance_scans: bool = True
    format_multiple_choice: bool = True
    smart_layout: bool = True


@router.get("/", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    db: Session = Depends(get_db)
):
    current_user = get_current_user_from_session(request, db)
    if not current_user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": None, "user": None}
        )

    user_tasks = db.query(Task).filter(Task.user_id == current_user.id).order_by(Task.created_at.desc()).limit(20).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": current_user,
            "recent_tasks": user_tasks
        }
    )


@router.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    filename = file.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng file .{ext} không được hỗ trợ. Vui lòng tải lên PDF hoặc ảnh (PNG, JPG, WEBP)."
        )

    task_id = str(uuid.uuid4())
    safe_name = f"{task_id}_{filename}"
    saved_path = os.path.join(UPLOADS_DIR, safe_name)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File vượt quá dung lượng tối đa cho phép ({MAX_FILE_SIZE_MB}MB)."
        )

    with open(saved_path, "wb") as f:
        f.write(content)

    file_type = "pdf" if ext == "pdf" else "image"

    task = Task(
        id=task_id,
        user_id=user.id,
        original_filename=filename,
        file_type=file_type,
        file_path=saved_path,
        status="pending",
        progress=0,
        current_step="Đã tải file lên máy chủ thành công."
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return {
        "success": True,
        "task_id": task.id,
        "filename": task.original_filename,
        "file_type": task.file_type
    }


@router.post("/api/tasks/{task_id}/start")
async def start_task_conversion(
    task_id: str,
    options: TaskStartRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ.")

    if task.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền thao tác trên tác vụ này.")

    if task.status == "processing":
        return {"success": True, "message": "Tác vụ đang được xử lý."}

    # Lưu options vào task
    task.set_options(options.model_dump())
    task.status = "pending"
    task.progress = 2
    task.current_step = "Đang đưa vào hàng đợi xử lý..."
    db.commit()

    # Kích hoạt worker chạy ngầm
    submit_task(task.id)

    return {"success": True, "message": "Đã bắt đầu tiến trình chuyển đổi.", "task_id": task.id}


@router.get("/api/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ.")

    if task.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập.")

    has_docx = bool(task.output_docx_path and os.path.exists(task.output_docx_path))

    return {
        "id": task.id,
        "filename": task.original_filename,
        "status": task.status,
        "progress": task.progress,
        "current_step": task.current_step,
        "total_pages": task.total_pages,
        "processed_pages": task.processed_pages,
        "has_docx": has_docx,
        "error_message": task.error_message,
        "logs": task.get_logs()
    }


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task_request(
    task_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ.")

    if task.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền thao tác.")

    cancel_task(task_id)
    task.status = "cancelled"
    task.current_step = "Đã dừng tác vụ bởi người dùng."
    db.commit()

    return {"success": True, "message": "Đã gửi lệnh dừng tiến trình."}


@router.get("/api/tasks/{task_id}/download")
async def download_task_docx(
    task_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ.")

    if task.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền tải file này.")

    if not task.output_docx_path or not os.path.exists(task.output_docx_path):
        raise HTTPException(status_code=404, detail="File kết quả (.docx) không tồn tại hoặc chưa xử lý xong.")

    download_name = f"{os.path.splitext(task.original_filename)[0]}_Word_MathType.docx"
    return FileResponse(
        path=task.output_docx_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.get("/api/history")
async def get_my_history(
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    tasks = db.query(Task).filter(Task.user_id == user.id).order_by(Task.created_at.desc()).limit(30).all()
    res = []
    for t in tasks:
        res.append({
            "id": t.id,
            "filename": t.original_filename,
            "file_type": t.file_type,
            "total_pages": t.total_pages,
            "status": t.status,
            "progress": t.progress,
            "has_docx": bool(t.output_docx_path and os.path.exists(t.output_docx_path)),
            "created_at": t.created_at.strftime("%d/%m/%Y %H:%M") if t.created_at else "-",
            "completed_at": t.completed_at.strftime("%d/%m/%Y %H:%M") if t.completed_at else "-"
        })
    return {"history": res}


@router.delete("/api/tasks/{task_id}")
async def delete_task(
    task_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ.")

    if task.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền xóa tác vụ này.")

    # Xóa file upload nếu còn
    if task.file_path and os.path.exists(task.file_path):
        try:
            os.remove(task.file_path)
        except Exception:
            pass

    db.delete(task)
    db.commit()
    return {"success": True, "message": "Đã xóa tác vụ thành công."}
