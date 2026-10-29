import os
import secrets

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(DATA_DIR, 'wordscan.db')}")

# Secret key for session signing
SECRET_KEY_FILE = os.path.join(DATA_DIR, ".secret_key")
if os.environ.get("SECRET_KEY"):
    SECRET_KEY = os.environ.get("SECRET_KEY")
elif os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, "r", encoding="utf-8") as f:
        SECRET_KEY = f.read().strip()
else:
    SECRET_KEY = secrets.token_hex(32)
    with open(SECRET_KEY_FILE, "w", encoding="utf-8") as f:
        f.write(SECRET_KEY)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE_MB = 100
