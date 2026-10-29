# Dockerfile for WordScan.me / MathScanToWord Web
FROM python:3.12-slim

# Thiết lập môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết cho OpenCV, MuPDF, và phông chữ
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    fonts-liberation \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Tạo thư mục dữ liệu và cấp quyền
RUN mkdir -p data/uploads data/output cache output

EXPOSE 8000

# Khởi chạy Web Server
CMD ["python", "run_web.py", "--host", "0.0.0.0", "--port", "8000"]
