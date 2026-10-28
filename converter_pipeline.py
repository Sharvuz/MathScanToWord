#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
================================================================================
PIPELINE CHUYỂN ĐỔI SÁCH SCAN PDF (TOÁN - KHTN) ~400 TRANG SANG WORD (.DOCX)
Tương thích 100% MathType Toggle TeX | Gemini Vision Key Pool | Checkpointing
================================================================================
Tác giả: Senior AI Engineer & Python Core Developer
"""

import os
import sys
import time
import json
import base64
import logging
import argparse
import io
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pymupdf as fitz
from PIL import Image
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

# Đảm bảo UTF-8 cho Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ==============================================================================
# 1. CẤU HÌNH LOGGING CHUYÊN NGHIỆP
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline_execution.log", encoding="utf-8", mode="a")
    ]
)
logger = logging.getLogger("MathScienceOCR")


# ==============================================================================
# 2. SYSTEM INSTRUCTION CHUYÊN BIỆT CHO TOÁN & KHOA HỌC TỰ NHIÊN (KHTN)
# ==============================================================================
SYSTEM_PROMPT = """Bạn là chuyên gia thị giác máy tính và số hóa tài liệu Toán học, Vật lý, Hóa học, Sinh học (KHTN) cấp 2 và cấp 3 tại Việt Nam.
Nhiệm vụ của bạn là bóc tách trang sách scan được cung cấp với độ chính xác học thuật 100%, trả về văn bản Markdown chứa công thức LaTeX chuẩn MathType và định vị Bounding Box cho tất cả các hình vẽ/sơ đồ/đồ thị.

QUY TẮC CỐT LÕI:
1. VĂN BẢN VÀ CÔNG THỨC TOÁN HỌC (CHUẨN MATHTYPE TOGGLE TEX):
- VĂN BẢN TIẾNG VIỆT THƯỜNG (Lời dẫn đề bài, câu hỏi, hướng dẫn giải, chọn đáp án):
  Viết tiếng Việt bình thường. TUYỆT ĐỐI KHÔNG bọc các từ tiếng Việt thông thường vào trong \\text{...} (như \\text{Câu}, \\text{Tam giác}, \\text{Chọn}, \\text{Áp dụng}, \\text{Giá trị}).
  TUYỆT ĐỐI KHÔNG bọc cả câu văn vào trong dấu $...$.
- CÔNG THỨC TOÁN HỌC: MỌI biểu thức, phương trình, số đo, phân số, đáp án trắc nghiệm BẮT BUỘC nằm trong $inline$ hoặc $$display$$.
  Ví dụ: Viết A. $\\dfrac{\\sqrt{55}}{2}$, TUYỆT ĐỐI KHÔNG viết cộc lốc A. \\frac{\\sqrt{55}}{2}.
  Phân số dùng \\dfrac{...}{...}, căn bậc n \\sqrt[n]{...}, hệ phương trình \\begin{cases} ... \\end{cases}.
- KÝ HIỆU HÌNH HỌC: Các điểm, đỉnh, cạnh, tam giác (A, B, C, K, M, N, AB, BC, AH, \\Delta ABC) là biến toán, viết $A$, $B$, $K$, $BC$, $\\Delta ABC$.
- KÝ TỰ Ô VUÔNG RỖNG: Nếu trang scan có ô vuông rỗng do lỗi font scan (như [□; 2] hoặc M(□; ...)), hãy khôi phục đúng ký tự toán học (như dấu trừ $[-1; 2]$) hoặc loại bỏ ô vuông vô nghĩa.
- \\text{...} CHỈ DÙNG khi nằm bên trong $...$ cho từ tiếng Việt hoặc đơn vị: $S_{\\text{tam giác}}$, $\\text{cm}$, $\\text{mét}$, $\\text{tuổi}$, $\\text{ƯCLN}(a;b)$.

2. VẬT LÝ & HÓA HỌC:
- Vật lý: Ký hiệu vectơ ($\\vec{F}, \\vec{v}, \\vec{a}$), chỉ số dưới ($F_{\\text{ms}}, U_{\\text{AB}}, R_1$), đơn vị ($\\Omega, \\mu F, \\text{m/s}^2$).
- Hóa học: Công thức chất và chỉ số ($Fe_2(SO_4)_3$, $Al^{3+}$, $SO_4^{2-}$).
  Phương trình hóa học dùng mũi tên: $2H_2 + O_2 \\xrightarrow{t^o} 2H_2O$, $Fe + 2HCl \\rightarrow FeCl_2 + H_2\\uparrow$, kết tủa $\\downarrow$, khí $\\uparrow$.

3. BẢNG BIỂU & HƯỚNG DẪN CHẤM:
- Chuyển toàn bộ bảng số liệu, bảng biến thiên, bảng đáp án/chấm điểm thành bảng Markdown chuẩn (| Cột 1 | Cột 2 | Cột 3 | kèm |---|---|---|).
- Xuống dòng bên trong ô bảng bắt buộc dùng thẻ <br>.

4. HÌNH MINH HỌA / ĐỒ THỊ / HÌNH HỌC / MẠCH ĐIỆN:
- TUYỆT ĐỐI KHÔNG vẽ lại hình bằng ký tự ASCII hay mã TikZ.
- Xác định tọa độ Bounding Box [ymin, xmin, ymax, xmax] trên thang chuẩn hóa 0 đến 1000 cho mọi hình vẽ, sơ đồ thí nghiệm, đồ thị.
- Đặt thẻ giữ chỗ [HINH_1], [HINH_2],... vào đúng vị trí tương ứng trong văn bản.

5. ĐỊNH DẠNG ĐẦU RA (JSON SCHEMA NGHIÊM NGẶT):
Chỉ trả về DUY NHẤT một chuỗi JSON hợp lệ không có markdown backtick bao ngoài:
{
  "figures": [
    {
      "id": "HINH_1",
      "box_2d": [ymin, xmin, ymax, xmax],
      "description": "Mô tả ngắn gọn"
    }
  ],
  "markdown": "Nội dung văn bản và công thức LaTeX hoàn chỉnh, chứa các thẻ [HINH_X]..."
}"""


# ==============================================================================
# 3. QUẢN LÝ TẢI VÀ API KEY POOL (ROUND-ROBIN & EXPONENTIAL BACKOFF)
# ==============================================================================
class APIKeyPool:
    """Quản lý danh sách API Key với thuật toán Round-Robin và Rate Limit Pacing."""
    def __init__(self, keys: List[str], min_request_interval: float = 1.5):
        self.keys = [k.strip() for k in keys if k.strip()]
        if not self.keys:
            raise ValueError("Danh sách API Key rỗng! Vui lòng cung cấp ít nhất 1 Gemini API Key.")
        self.current_idx = 0
        self.min_interval = min_request_interval
        self.last_request_time: Dict[int, float] = {i: 0.0 for i in range(len(self.keys))}

    def get_current_key(self) -> Tuple[int, str]:
        return self.current_idx + 1, self.keys[self.current_idx]

    def get_key_by_idx(self, idx: int) -> Tuple[int, str]:
        real_idx = idx % len(self.keys)
        return real_idx + 1, self.keys[real_idx]

    def rotate_to_next(self, reason: str = "") -> Tuple[int, str]:
        old_idx = self.current_idx
        self.current_idx = (self.current_idx + 1) % len(self.keys)
        logger.warning(f"Đổi API Key: Key {old_idx + 1} ➔ Key {self.current_idx + 1} ({reason})")
        return self.get_current_key()

    def pace_request(self, key_idx: Optional[int] = None):
        """Đảm bảo không gọi quá giới hạn 15 RPM của Free Tier."""
        target_idx = (key_idx if key_idx is not None else self.current_idx) % len(self.keys)
        elapsed = time.time() - self.last_request_time[target_idx]
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time[target_idx] = time.time()


# ==============================================================================
# 4. TRÍCH XUẤT ẢNH PDF (300 DPI) & CROP HÌNH HỌC (PILLOW)
# ==============================================================================
class VisionProcessor:
    @staticmethod
    def render_pdf_page_to_png(pdf_path: str, page_number: int, dpi: int = 300, output_dir: str = "cache/pages") -> str:
        """Trích xuất 1 trang PDF thành ảnh PNG ở độ phân giải cao 300 DPI."""
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f"page_{page_number:04d}.png")
        if os.path.exists(out_path):
            return out_path

        doc = fitz.open(pdf_path)
        if page_number < 1 or page_number > len(doc):
            doc.close()
            raise IndexError(f"Trang {page_number} vượt quá tổng số trang {len(doc)} của file PDF.")

        page = doc.load_page(page_number - 1)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        doc.close()

        # Tự động phát hiện và xoay thẳng nếu trang scan bị đặt ngang/dọc (90/270 độ)
        try:
            from core.image_preprocessor import ImagePreprocessor
            cv_img = ImagePreprocessor.pil_to_cv2(img)
            cv_img, _ = ImagePreprocessor.detect_and_fix_orientation(cv_img)
            img = ImagePreprocessor.cv2_to_pil(cv_img)
        except Exception as e:
            logger.warning(f"Không thể kiểm tra hướng trang tự động: {str(e)}")

        img.save(out_path, "PNG", quality=95)
        return out_path

    @staticmethod
    def crop_figure(
        page_image_path: str,
        box_2d: List[float],
        output_dir: str,
        page_num: int,
        fig_idx: int,
        padding: int = 10
    ) -> str:
        """
        Crop hình vẽ dựa trên Bounding Box chuẩn hóa [ymin, xmin, ymax, xmax] (thang 0-1000).
        Lưu vào thư mục output_images/ với định danh: page_X_hinh_Y.png.
        """
        os.makedirs(output_dir, exist_ok=True)
        out_filename = f"page_{page_num}_hinh_{fig_idx}.png"
        out_path = os.path.join(output_dir, out_filename)

        with Image.open(page_image_path) as img:
            from core.image_cropper import ImageCropper
            out_path, _ = ImageCropper.crop_figure(img, box_2d, out_path, auto_refine=True)

        return out_path


# ==============================================================================
# 5. BỘ GỌI GEMINI API VỚI EXPONENTIAL BACKOFF & CHUYỂN KEY
# ==============================================================================
class GeminiClient:
    def __init__(self, key_pool: APIKeyPool, model: str = "gemini-3.5-flash-lite"):
        self.key_pool = key_pool
        self.model = model

    def process_page(self, page_image_path: str, page_num: int, preferred_key_idx: Optional[int] = None) -> Dict[str, Any]:
        """Gửi ảnh trang sách lên Gemini với cơ chế Exponential Backoff & Retry."""
        with open(page_image_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        max_attempts = max(6, len(self.key_pool.keys) * 2)
        base_delay = 2.5
        local_idx = (preferred_key_idx if preferred_key_idx is not None else self.key_pool.current_idx) % len(self.key_pool.keys)

        for attempt in range(1, max_attempts + 1):
            key_id, api_key = self.key_pool.get_key_by_idx(local_idx)
            self.key_pool.pace_request(local_idx)

            start_t = time.time()
            logger.info(f"[Trang {page_num}] Đang gửi yêu cầu bằng Key {key_id} (Lần thử {attempt}/{max_attempts})...")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": api_key
            }
            payload = {
                "systemInstruction": {
                    "parts": [{"text": SYSTEM_PROMPT}]
                },
                "contents": [
                    {
                        "parts": [
                            {"text": f"Hãy bóc tách chính xác toàn bộ nội dung học thuật trang số {page_num} này theo cấu trúc JSON."},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": img_base64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1
                }
            }

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=75)
                elapsed = time.time() - start_t

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        logger.warning(f"[Trang {page_num}] Google API chặn yêu cầu (không có candidates)")
                        local_idx = (local_idx + 1) % len(self.key_pool.keys)
                        time.sleep(2)
                        continue

                    cand = candidates[0]
                    parts = cand.get("content", {}).get("parts", [])
                    finish_reason = cand.get("finishReason", "")
                    if not parts:
                        if finish_reason == "RECITATION":
                            logger.warning(f"[Trang {page_num}] ⚠️ Bị chặn bởi bộ lọc bản quyền Google (Recitation). Đang thử lại với key khác...")
                        else:
                            logger.warning(f"[Trang {page_num}] API phản hồi không có nội dung (finishReason: {finish_reason})")
                        local_idx = (local_idx + 1) % len(self.key_pool.keys)
                        time.sleep(2)
                        continue

                    raw_text = parts[0].get("text", "")
                    parsed = self._parse_json_safe(raw_text)
                    logger.info(f"[Trang {page_num}] Xử lý thành công bằng Key {key_id} ({elapsed:.1f}s)")
                    if elapsed > 15.0 and len(self.key_pool.keys) > 1:
                        self.key_pool.rotate_to_next(f"Thời gian xử lý {elapsed:.1f}s > 15s")
                    return parsed

                elif response.status_code in [429, 503]:
                    logger.warning(f"[Trang {page_num}] Key {key_id} gặp mã lỗi HTTP {response.status_code} (Rate Limit / Quá tải)")
                    local_idx = (local_idx + 1) % len(self.key_pool.keys)
                    wait_time = min(12.0, base_delay * attempt)
                    time.sleep(wait_time)

                else:
                    logger.error(f"[Trang {page_num}] Key {key_id} báo lỗi HTTP {response.status_code}: {response.text[:100]}")
                    local_idx = (local_idx + 1) % len(self.key_pool.keys)
                    time.sleep(base_delay)

            except requests.exceptions.Timeout:
                logger.warning(f"[Trang {page_num}] Key {key_id} bị quá thời gian chờ (Timeout > 75s)")
                local_idx = (local_idx + 1) % len(self.key_pool.keys)
            except Exception as e:
                logger.error(f"[Trang {page_num}] Lỗi ngoại lệ: {str(e)}")
                local_idx = (local_idx + 1) % len(self.key_pool.keys)
                time.sleep(base_delay)

        raise RuntimeError(f"Trang {page_num} thất bại sau {max_attempts} lần thử với các API Key.")

    @staticmethod
    def _fix_json_latex_escapes(text: str) -> str:
        r"""
        Fixes unescaped LaTeX commands in JSON strings where single backslashes collide
        with standard JSON escape codes (\t, \f, \b, \r, \n).
        Without this, \text becomes \x09ext (TAB + 'ext'), \frac becomes \x0crac (FF + 'rac'), etc.
        """
        latex_cmds = (
            r'text|textbf|textit|texttt|tfrac|tan|tanh|theta|times|to|tau|top|triangle|'
            r'dfrac|frac|forall|'
            r'bar|beta|begin|binom|mathbf|boldsymbol|bullet|bot|'
            r'right|rho|rangle|rightarrow|Rightarrow|'
            r'neq|nabla|neg|notin'
        )
        pattern = rf'(?<!\\)\\({latex_cmds})\b'
        return re.sub(pattern, r'\\\\\1', text)

    def _parse_json_safe(self, text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Fix unescaped LaTeX commands before json.loads so \t, \f, \b etc. are not eaten
        cleaned = self._fix_json_latex_escapes(cleaned)

        # 1. Thử json.loads tiêu chuẩn
        try:
            res = json.loads(cleaned)
            if isinstance(res, dict) and "markdown" in res:
                return {
                    "markdown": res.get("markdown", ""),
                    "figures": res.get("figures", [])
                }
        except Exception:
            pass

        # 2. Xử lý lỗi backslash LaTeX bằng Regex Parser chuyên sâu
        figures = []
        fig_match = re.search(r'"figures"\s*:\s*(\[\s*\{.*?\}\s*\])', cleaned, flags=re.DOTALL)
        if fig_match:
            try:
                figures = json.loads(fig_match.group(1))
            except Exception:
                pass

        md_text = ""
        md_match = re.search(r'"markdown"\s*:\s*"(.*)"\s*\}\s*$', cleaned, flags=re.DOTALL)
        if md_match:
            md_text = md_match.group(1)
            # Unescape JSON escaped newlines and quotes
            md_text = md_text.replace(r'\n', '\n').replace(r'\"', '"')
        else:
            md_text = cleaned

        return {"markdown": md_text, "figures": figures}


# ==============================================================================
# 6. CƠ CHẾ CHỐNG MẤT DỮ LIỆU (CHECKPOINTING)
# ==============================================================================
class CheckpointManager:
    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def is_page_done(self, page_num: int) -> bool:
        path = os.path.join(self.checkpoint_dir, f"page_{page_num:04d}.json")
        return os.path.exists(path)

    @staticmethod
    def _fix_json_latex_escapes(text: str) -> str:
        latex_cmds = (
            r'text|textbf|textit|texttt|tfrac|tan|tanh|theta|times|to|tau|top|triangle|'
            r'dfrac|frac|forall|'
            r'bar|beta|begin|binom|mathbf|boldsymbol|bullet|bot|'
            r'right|rho|rangle|rightarrow|Rightarrow|'
            r'neq|nabla|neg|notin'
        )
        pattern = rf'(?<!\\)\\({latex_cmds})\b'
        return re.sub(pattern, r'\\\\\1', text)

    def load_checkpoint(self, page_num: int) -> Optional[Dict[str, Any]]:
        path = os.path.join(self.checkpoint_dir, f"page_{page_num:04d}.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read()
                raw = self._fix_json_latex_escapes(raw)
                return json.loads(raw)
            except Exception:
                return None
        return None

    def save_checkpoint(self, page_num: int, data: Dict[str, Any]):
        path = os.path.join(self.checkpoint_dir, f"page_{page_num:04d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ==============================================================================
# 7. BỘ TỔNG HỢP VĂN BẢN VÀ XUẤT RA MICROSOFT WORD (.DOCX)
# ==============================================================================
class DocxSynthesizer:
    def __init__(self, font_name: str = "Times New Roman", font_size_pt: float = 13.0):
        self.doc = docx.Document()
        self.font_name = font_name
        self.font_size_pt = font_size_pt
        self._setup_margins_and_styles()

    def _setup_margins_and_styles(self):
        # Khổ A4, lề 2cm (~0.79 inch)
        for s in self.doc.sections:
            s.top_margin = Inches(0.79)
            s.bottom_margin = Inches(0.79)
            s.left_margin = Inches(0.79)
            s.right_margin = Inches(0.79)

        style = self.doc.styles['Normal']
        style.font.name = self.font_name
        style.font.size = Pt(self.font_size_pt)
        style.paragraph_format.line_spacing = 1.15
        style.paragraph_format.space_after = Pt(3)

    def synthesize_document(self, pages_data: List[Dict[str, Any]], output_docx: str):
        """
        Ghép toàn bộ trang theo thứ tự từ 1 đến 400.
        Giữ nguyên $formula$ cho MathType Toggle TeX, chèn ảnh căn giữa và ngắt trang.
        """
        total = len(pages_data)
        for idx, p_info in enumerate(pages_data):
            page_num = p_info["page"]
            markdown = p_info["markdown"]
            image_map = p_info.get("images", {})

            self._render_page_content(markdown, image_map)

            # Thêm ngắt trang giữa các trang (trừ trang cuối cùng)
            if idx < total - 1:
                self.doc.add_page_break()

        os.makedirs(os.path.dirname(os.path.abspath(output_docx)), exist_ok=True)
        self.doc.save(output_docx)
        logger.info(f"Đã xuất file Word hoàn chỉnh thành công tại: {output_docx}")

    def _render_page_content(self, markdown_text: str, image_map: Dict[str, str]):
        # Chuẩn hóa ngắt dòng
        lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Bảng Markdown (Bảng đáp án, chấm điểm, bảng số liệu)
            if line.startswith("|") and "|" in line[1:]:
                table_lines = []
                while i < len(lines):
                    l_str = lines[i].strip()
                    if not l_str:
                        if table_lines and table_lines[-1].endswith("|"):
                            break
                        i += 1
                        continue
                    if l_str.startswith("|"):
                        if table_lines and not table_lines[-1].endswith("|"):
                            table_lines[-1] += " " + l_str
                        else:
                            table_lines.append(l_str)
                    else:
                        if table_lines:
                            table_lines[-1] += " " + l_str
                        else:
                            break
                    i += 1

                if table_lines:
                    self._render_table(table_lines, image_map)
                continue

            # Kiểm tra placeholder hình ảnh [HINH_X]
            fig_match = re.search(r'\[(HINH_\d+)\]', line)
            if fig_match:
                fig_id = fig_match.group(1)
                before_t = line[:fig_match.start()].strip()
                if before_t:
                    self._add_paragraph_with_bold(before_t)

                if fig_id in image_map and os.path.exists(image_map[fig_id]):
                    self._insert_centered_image(image_map[fig_id])

                after_t = line[fig_match.end():].strip()
                if after_t:
                    self._add_paragraph_with_bold(after_t)

                i += 1
                continue

            # Tiêu đề Headings
            if line.startswith("# "):
                p = self.doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(4)
                run = p.add_run(line[2:].strip())
                run.bold = True
                run.font.size = Pt(self.font_size_pt + 3)
                run.font.color.rgb = RGBColor(0, 32, 96)
            elif line.startswith("## ") or line.startswith("### "):
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(3)
                pref = 3 if line.startswith("## ") else 4
                run = p.add_run(line[pref:].strip())
                run.bold = True
                run.font.size = Pt(self.font_size_pt + 1)
                run.font.color.rgb = RGBColor(0, 32, 96)
            else:
                self._add_paragraph_with_bold(line)

            i += 1

    def _add_paragraph_with_bold(self, text: str):
        p = self.doc.add_paragraph()
        parts = re.split(r'(\*\*.*?\*\*)', text)
        for part in parts:
            if not part:
                continue
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                run = p.add_run(part[2:-2])
                run.bold = True
            else:
                run = p.add_run(part)
            run.font.name = self.font_name
            run.font.size = Pt(self.font_size_pt)

    def _insert_centered_image(self, img_path: str):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run()
        # Khổ ảnh ~3.2 inch (~8cm) cân đối trang A4
        run.add_picture(img_path, width=Inches(3.2))

    def _render_table(self, table_lines: List[str], image_map: Dict[str, str]):
        parsed_rows = []
        for line in table_lines:
            if re.match(r'^\|[\s\-:]+(\|[\s\-:]+)+\|$', line):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            parsed_rows.append(cells)

        if not parsed_rows:
            return

        col_count = max(len(r) for r in parsed_rows)
        for r in parsed_rows:
            while len(r) < col_count:
                r.append("")

        tbl = self.doc.add_table(rows=len(parsed_rows), cols=col_count)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.style = 'Table Grid'

        # Chiều rộng cột
        if col_count == 3:
            col_widths = [Inches(1.0), Inches(5.0), Inches(0.8)]
        else:
            col_widths = [Inches(6.8 / col_count)] * col_count

        for r_idx, row_data in enumerate(parsed_rows):
            is_hdr = (r_idx == 0)
            tr = tbl.rows[r_idx]._tr
            if is_hdr:
                tr.get_or_add_trPr().append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))

            for c_idx, cell_val in enumerate(row_data):
                cell = tbl.cell(r_idx, c_idx)
                cell.width = col_widths[min(c_idx, len(col_widths) - 1)]
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

                if is_hdr:
                    cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="F0F0F0"/>'))

                p = cell.paragraphs[0]
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)

                if is_hdr or c_idx == 0 or (col_count == 3 and c_idx == 2):
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

                # Xử lý xuống dòng <br> trong ô
                sub_parts = re.split(r'<br\s*/?>', cell_val, flags=re.IGNORECASE)
                for s_idx, sp in enumerate(sub_parts):
                    sp_clean = sp.strip()
                    if not sp_clean and s_idx > 0:
                        continue
                    cur_p = p if s_idx == 0 else cell.add_paragraph()
                    cur_p.paragraph_format.line_spacing = 1.15
                    cur_p.paragraph_format.space_before = Pt(2)
                    cur_p.paragraph_format.space_after = Pt(2)
                    if is_hdr or c_idx == 0 or (col_count == 3 and c_idx == 2):
                        cur_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

                    # Kiểm tra hình trong ô bảng
                    f_match = re.search(r'\[(HINH_\d+)\]', sp_clean)
                    if f_match and f_match.group(1) in image_map:
                        im_p = image_map[f_match.group(1)]
                        if os.path.exists(im_p):
                            r_im = cur_p.add_run()
                            r_im.add_picture(im_p, width=Inches(2.5))
                    else:
                        parts = re.split(r'(\*\*.*?\*\*)', sp_clean)
                        for part in parts:
                            if not part:
                                continue
                            if part.startswith("**") and part.endswith("**"):
                                run = cur_p.add_run(part[2:-2])
                                run.bold = True
                            else:
                                run = cur_p.add_run(part)
                            if is_hdr:
                                run.bold = True
                            run.font.name = self.font_name
                            run.font.size = Pt(self.font_size_pt)


# ==============================================================================
# 8. PIPELINE ĐIỀU PHỐI CHÍNH (MASTER CONTROLLER)
# ==============================================================================
def load_default_keys() -> List[str]:
    """Tự động nạp API Key từ config.json hoặc biến môi trường."""
    keys = []
    # 1. Kiểm tra config.json trong thư mục
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                keys.extend(cfg.get("api_keys", []))
        except Exception:
            pass

    # 2. Kiểm tra biến môi trường
    env_keys = os.environ.get("GEMINI_API_KEYS") or os.environ.get("GEMINI_API_KEY", "")
    if env_keys:
        for k in env_keys.split(","):
            if k.strip():
                keys.append(k.strip())

    return [k.strip() for k in keys if k.strip()]


def parse_page_range(range_str: str, max_pages: int) -> List[int]:
    if not range_str or range_str.lower() == "all":
        return list(range(1, max_pages + 1))
    pages = set()
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            s, e = map(int, part.split("-"))
            for p in range(min(s, e), max(s, e) + 1):
                if 1 <= p <= max_pages:
                    pages.add(p)
        else:
            p = int(part)
            if 1 <= p <= max_pages:
                pages.add(p)
    return sorted(list(pages)) if pages else list(range(1, max_pages + 1))


def run_pipeline(
    pdf_path: str,
    output_docx: Optional[str] = None,
    page_range_str: str = "all",
    model: str = "gemini-3.5-flash-lite",
    workers: Optional[int] = None
):
    logger.info("=" * 70)
    logger.info("KHỞI CHẠY PIPELINE SỐ HÓA SÁCH TOÁN - KHTN SANG WORD")
    logger.info(f"File PDF nguồn: {pdf_path}")
    logger.info(f"Model Gemini: {model}")
    logger.info("=" * 70)

    # 1. Nạp và khởi tạo Key Pool
    keys = load_default_keys()
    logger.info(f"Đã nhận diện {len(keys)} Gemini API Key trong hệ thống.")
    key_pool = APIKeyPool(keys, min_request_interval=1.5)
    gemini_client = GeminiClient(key_pool=key_pool, model=model)

    # 2. Khởi tạo Quản lý Checkpoints & Thư mục ảnh
    checkpoint_mgr = CheckpointManager(checkpoint_dir="checkpoints")
    output_images_dir = "output_images"
    os.makedirs(output_images_dir, exist_ok=True)

    # 3. Đọc số trang PDF
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()
    logger.info(f"Tài liệu PDF có tổng cộng: {total_pages} trang.")

    target_pages = parse_page_range(page_range_str, total_pages)
    logger.info(f"Số trang được lên lịch xử lý: {len(target_pages)} trang (Dải trang: {target_pages[0]} ➔ {target_pages[-1]})")

    # Xác định số luồng song song
    num_workers = workers if workers and workers > 0 else len(keys)
    num_workers = max(1, min(num_workers, len(target_pages)))
    logger.info(f"🚀 Kích hoạt {num_workers} luồng xử lý song song (Multi-Threading x{num_workers}).")

    # 4. Tiền kết xuất trước ảnh các trang (Pre-render) để tránh xung đột file PyMuPDF
    logger.info("Đang kiểm tra và kết xuất trước ảnh chất lượng cao 300 DPI...")
    for p_num in target_pages:
        VisionProcessor.render_pdf_page_to_png(pdf_path, p_num, dpi=300)

    # 5. Hàm xử lý 1 trang sách
    def process_single_page(page_num: int, worker_idx: int) -> Dict[str, Any]:
        # Kiểm tra Checkpoint (Cache)
        if checkpoint_mgr.is_page_done(page_num):
            cached = checkpoint_mgr.load_checkpoint(page_num)
            if cached:
                logger.info(f"[Trang {page_num}] Đã hoàn thành từ trước (Loaded từ Checkpoint Cache).")
                return cached

        page_png = os.path.join("cache/pages", f"page_{page_num:04d}.png")
        if not os.path.exists(page_png):
            page_png = VisionProcessor.render_pdf_page_to_png(pdf_path, page_num, dpi=300)

        # Gọi Gemini với Key Affinity
        gemini_data = gemini_client.process_page(page_png, page_num, preferred_key_idx=worker_idx)
        markdown_text = gemini_data.get("markdown", "")
        raw_figures = gemini_data.get("figures", [])

        # Crop hình vẽ & Lọc hình rỗng/nhiễu
        page_images_map = {}
        for f_idx, fig in enumerate(raw_figures, start=1):
            box = fig.get("box_2d", [0, 0, 1000, 1000])
            fig_id = fig.get("id", f"HINH_{f_idx}")
            crop_path = VisionProcessor.crop_figure(
                page_image_path=page_png,
                box_2d=box,
                output_dir=output_images_dir,
                page_num=page_num,
                fig_idx=f_idx
            )
            from core.image_cropper import ImageCropper
            is_blank, reject_reason = ImageCropper.is_blank_or_noise(crop_path)
            if is_blank:
                logger.warning(f"[Trang {page_num}] 🗑 Đã lọc hình rác/trắng [{fig_id}] ({reject_reason})")
            else:
                # Tự động AI vẽ lại hình học chuẩn trực diện nếu phát hiện là bài hình
                from core.ai_figure_artist import AIGeometryArtist
                desc = fig.get("description", "")
                if AIGeometryArtist.is_likely_geometry(desc, context_text=markdown_text):
                    logger.info(f"[Trang {page_num}] ✨ Đang dùng AI vẽ lại hình học [{fig_id}] chuẩn trực diện...")
                    target_redraw = os.path.join(output_images_dir, f"page_{page_num}_hinh_{f_idx}_ai_redraw.png")
                    keys_list = [k for _, k in key_pool.keys]
                    rd_path = AIGeometryArtist.redraw_figure(
                        image_path=crop_path,
                        output_path=target_redraw,
                        api_keys=keys_list,
                        model=getattr(gemini_client, 'model', 'gemini-2.5-flash'),
                        description=desc,
                        context_text=markdown_text[:400]
                    )
                    if rd_path and os.path.exists(rd_path):
                        crop_path = rd_path
                        logger.info(f"[Trang {page_num}] ✅ Đã vẽ lại hình học [{fig_id}] thành công (vector 300 DPI)!")

                page_images_map[fig_id] = crop_path
                logger.info(f"[Trang {page_num}] Đã chèn hình minh họa: {os.path.basename(crop_path)}")

        page_record = {
            "page": page_num,
            "markdown": markdown_text,
            "images": page_images_map
        }
        checkpoint_mgr.save_checkpoint(page_num, page_record)
        return page_record

    # 6. Chạy ThreadPoolExecutor
    page_records_map = {}
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_page = {}
        for idx, page_num in enumerate(target_pages):
            worker_idx = idx % len(keys)
            fut = executor.submit(process_single_page, page_num, worker_idx)
            future_to_page[fut] = page_num

        for future in as_completed(future_to_page):
            p_num = future_to_page[future]
            try:
                rec = future.result()
                page_records_map[p_num] = rec
                logger.info(f"✓ Đã hoàn thành trang {p_num} ({len(page_records_map)}/{len(target_pages)})")
            except Exception as e:
                logger.error(f"✗ Thất bại khi xử lý trang {p_num}: {e}")
                raise e

    # 7. Sắp xếp lại danh sách kết quả đúng theo thứ tự trang 1..N
    pages_results = [page_records_map[p_num] for p_num in target_pages if p_num in page_records_map]

    # 8. Tổng hợp ra file Word (.docx)
    if not output_docx:
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_docx = os.path.join("output", f"{base_name}_Full_MathType.docx")

    logger.info("=" * 70)
    logger.info("ĐANG TỔNG HỢP VĂN BẢN VÀ XUẤT RA FILE WORD (.DOCX)...")
    synthesizer = DocxSynthesizer(font_name="Times New Roman", font_size_pt=13.0)
    synthesizer.synthesize_document(pages_results, output_docx)

    logger.info("=" * 70)
    logger.info("HOÀN TẤT 100% TIẾN TRÌNH!")
    logger.info(f"File kết quả: {os.path.abspath(output_docx)}")
    logger.info("=" * 70)


# ==============================================================================
# 9. CLI ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline chuyển đổi PDF scan sách Toán - KHTN sang Word MathType.")
    parser.add_argument("pdf_path", type=str, help="Đường dẫn tới file PDF scan sách cần chuyển đổi.")
    parser.add_argument("-o", "--output", type=str, default=None, help="Đường dẫn file Word đầu ra (.docx).")
    parser.add_argument("-p", "--pages", type=str, default="all", help="Dải trang cần xử lý (ví dụ: '1-30', '1-10,15,20-40', 'all').")
    parser.add_argument("-m", "--model", type=str, default="gemini-3.5-flash-lite", help="Model Gemini (mặc định: gemini-3.5-flash-lite).")
    parser.add_argument("-w", "--workers", type=int, default=3, help="Số luồng chạy song song (mặc định: 3).")

    args = parser.parse_args()
    if not os.path.exists(args.pdf_path):
        logger.error(f"Không tìm thấy file: {args.pdf_path}")
        sys.exit(1)

    run_pipeline(
        pdf_path=args.pdf_path,
        output_docx=args.output,
        page_range_str=args.pages,
        model=args.model,
        workers=args.workers
    )
