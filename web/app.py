import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from web.config import SECRET_KEY, BASE_DIR
from web.database import init_db
from web.security import ensure_default_admin
from web.routes import auth, admin, convert


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo database và tài khoản admin mặc định
    init_db()
    ensure_default_admin()
    yield


app = FastAPI(
    title="WordScan.me - Hệ thống Số Hóa Sách Scan & Đề Thi Toán Sang Word",
    description="Cổng web chuyển đổi tài liệu Toán - KHTN chuẩn OMML/MathType cho trung tâm giáo dục.",
    version="2.0.0",
    lifespan=lifespan
)

# Cookie session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="wordscan_session",
    max_age=86400 * 7,  # 7 days
    same_site="lax",
    https_only=False
)

# Mount static files
static_dir = os.path.join(BASE_DIR, "web", "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Include routes
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(convert.router)
