#!/bin/bash
# Script tự động cập nhật hệ thống WordScan.me trên VPS Linux
set -e

echo "=========================================================="
echo "  DANG CAP NHAT HE THONG WORDSAN.ME LEN PHIEN BAN MOI NHAT"
echo "=========================================================="

echo "[1/3] Kéo mã nguồn mới nhất từ GitHub..."
git pull origin main

echo "[2/3] Build lại Docker image và khởi động lại container..."
docker compose down
docker compose up -d --build

echo "[3/3] Dọn dẹp image cũ..."
docker image prune -f

echo "=========================================================="
echo "  CAP NHAT THANH CONG! HE THONG DANG HOAT DONG TAI https://wordscan.me"
echo "=========================================================="
