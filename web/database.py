import json
from datetime import datetime
from typing import Generator
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from web.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    full_name = Column(String(128), default="")
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), default="teacher", nullable=False)  # 'admin' or 'teacher'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(10), default="pdf")
    file_path = Column(String(512), nullable=False)
    total_pages = Column(Integer, default=1)
    processed_pages = Column(Integer, default=0)
    status = Column(String(20), default="pending", index=True)  # pending, processing, completed, failed, cancelled
    progress = Column(Integer, default=0)  # 0-100%
    current_step = Column(String(255), default="Đang chờ khởi chạy...")
    output_docx_path = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    logs_json = Column(Text, default="[]")
    options_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="tasks")

    def get_logs(self):
        try:
            return json.loads(self.logs_json or "[]")
        except Exception:
            return []

    def set_logs(self, logs: list):
        self.logs_json = json.dumps(logs, ensure_ascii=False)

    def get_options(self):
        try:
            return json.loads(self.options_json or "{}")
        except Exception:
            return {}

    def set_options(self, opts: dict):
        self.options_json = json.dumps(opts, ensure_ascii=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True, index=True)
    value = Column(Text, nullable=False)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
