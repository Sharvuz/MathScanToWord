import os
import sys
import json
import time
import uuid
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

from web.database import SessionLocal, Task, SystemSetting
from web.config import OUTPUT_DIR, DATA_DIR, BASE_DIR

logger = logging.getLogger("WebTaskManager")

# In-memory tracking for running tasks and cancellation tokens
ACTIVE_WORKERS: Dict[str, bool] = {}  # task_id -> is_running flag


def get_system_settings() -> dict:
    """Load settings from DB or fall back to config.json or environment."""
    settings = {
        "api_keys": [],
        "model": "gemini-2.5-flash",
        "slow_threshold_seconds": 30,
        "concurrent_workers": 3,
        "options": {
            "create_word": True,
            "normalize_gemini": True,
            "compact_paper_saver": True,
            "ai_geometry_redraw": True,
            "detect_and_insert_images": True,
            "auto_detect_columns": True,
            "enhance_scans": True,
            "format_multiple_choice": True,
            "smart_layout": True,
            "mcmix_compat": False,
            "export_tex": False
        }
    }

    # 1. Fallback to config.json
    config_file = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cf = json.load(f)
                settings.update(cf)
        except Exception as e:
            logger.warning(f"Không thể đọc config.json: {e}")

    # 2. Fallback to settings.json in DATA_DIR
    settings_file = os.path.join(DATA_DIR, "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                sf = json.load(f)
                if sf.get("api_keys"):
                    settings["api_keys"] = sf["api_keys"]
                if sf.get("model"):
                    settings["model"] = sf["model"]
                if sf.get("concurrent_workers"):
                    settings["concurrent_workers"] = sf["concurrent_workers"]
        except Exception:
            pass

    # 3. Fallback to Environment Variables (Render / Cloud permanent storage)
    env_keys_raw = os.environ.get("GEMINI_API_KEYS") or os.environ.get("GEMINI_API_KEY") or ""
    if env_keys_raw:
        cleaned = env_keys_raw.replace("\r\n", "\n").replace("\r", "\n").replace(";", ",")
        env_keys = []
        for line in cleaned.split("\n"):
            for k in line.split(","):
                cand = k.strip().strip("'\"")
                if cand and cand not in env_keys:
                    env_keys.append(cand)
        if env_keys:
            settings["api_keys"] = env_keys

    if os.environ.get("GEMINI_MODEL"):
        settings["model"] = os.environ.get("GEMINI_MODEL").strip()

    if os.environ.get("CONCURRENT_WORKERS"):
        try:
            settings["concurrent_workers"] = int(os.environ.get("CONCURRENT_WORKERS"))
        except Exception:
            pass

    # 4. Override from Database if present
    db = SessionLocal()
    try:
        db_keys = db.query(SystemSetting).filter(SystemSetting.key == "api_keys").first()
        if db_keys and db_keys.value:
            try:
                parsed_keys = json.loads(db_keys.value)
                if parsed_keys and len(parsed_keys) > 0:
                    settings["api_keys"] = parsed_keys
            except Exception:
                pass

        db_model = db.query(SystemSetting).filter(SystemSetting.key == "model").first()
        if db_model and db_model.value:
            settings["model"] = db_model.value

        db_workers = db.query(SystemSetting).filter(SystemSetting.key == "concurrent_workers").first()
        if db_workers and db_workers.value:
            try:
                settings["concurrent_workers"] = int(db_workers.value)
            except Exception:
                pass
    finally:
        db.close()

    return settings


class TaskWorker:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.db = SessionLocal()
        self.is_running = True
        ACTIVE_WORKERS[task_id] = True

    def emit_log(self, task: Task, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            "time": timestamp,
            "message": message,
            "level": level
        }
        logs = task.get_logs()
        logs.append(log_entry)
        task.set_logs(logs[-500:])
        task.current_step = message[:250]
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()

    def run(self):
        try:
            task = self.db.query(Task).filter(Task.id == self.task_id).first()
            if not task:
                logger.error(f"Task {self.task_id} không tồn tại trong DB.")
                return

            task.status = "processing"
            task.progress = 5
            self.emit_log(task, f"🚀 Bắt đầu tiếp nhận file: {task.original_filename}")

            sys_settings = get_system_settings()
            opts = task.get_options()
            merged_opts = dict(sys_settings.get("options", {}))
            merged_opts.update(opts)

            api_keys = sys_settings.get("api_keys", [])
            if not api_keys:
                raise ValueError(
                    "Hệ thống chưa được cấu hình Google Gemini API Key. Quản trị viên vui lòng vào mục 'Quản Trị Trung Tâm' -> 'Cấu Hình API Key & Model' để nhập key."
                )

            model = sys_settings.get("model", "gemini-2.5-flash")
            threshold = float(sys_settings.get("slow_threshold_seconds", 30))

            from core.gemini_engine import GeminiEngine
            from core.pdf_processor import PDFProcessor
            from core.image_preprocessor import ImagePreprocessor
            from core.image_cropper import ImageCropper
            from core.word_builder import WordBuilder
            from core.cache_manager import CacheManager
            from core.latex_formatter import LatexFormatter

            doc_dir = os.path.join(DATA_DIR, "cache", f"task_{self.task_id}")
            os.makedirs(doc_dir, exist_ok=True)
            cache_mgr = CacheManager()

            engine = GeminiEngine(
                api_keys=api_keys,
                model=model,
                slow_threshold_seconds=threshold,
                log_callback=lambda msg, lvl: self.emit_log(task, msg, lvl)
            )

            file_path = task.file_path
            is_pdf = task.file_type == "pdf" or file_path.lower().endswith(".pdf")

            # 1. Xác định số trang & dải trang cần xử lý (Page Range Selector)
            pages_to_process = []
            if is_pdf:
                try:
                    total_p = PDFProcessor.get_page_count(file_path)
                except Exception:
                    try:
                        import pymupdf as fitz
                        with fitz.open(file_path) as doc:
                            total_p = len(doc)
                    except Exception:
                        total_p = 1
                task.total_pages = total_p

                page_mode = merged_opts.get("page_mode", "all")
                if page_mode == "custom":
                    p_from = merged_opts.get("page_from")
                    p_to = merged_opts.get("page_to")
                    p_range_str = merged_opts.get("page_range", "")

                    if p_from is not None and p_to is not None and int(p_from) > 0 and int(p_to) > 0:
                        range_str = f"{p_from}-{p_to}"
                    elif p_range_str and p_range_str.strip():
                        range_str = str(p_range_str).strip()
                    else:
                        range_str = "all"

                    pages_to_process = PDFProcessor.parse_page_ranges(range_str, total_p)
                else:
                    pages_to_process = list(range(1, total_p + 1))

                if not pages_to_process:
                    pages_to_process = list(range(1, total_p + 1))
            else:
                task.total_pages = 1
                pages_to_process = [1]

            self.db.commit()

            range_summary = f"{pages_to_process[0]}-{pages_to_process[-1]}" if len(pages_to_process) > 1 else f"{pages_to_process[0]}"
            self.emit_log(task, f"📑 Đã chọn xử lý {len(pages_to_process)} trang (Dải trang: {range_summary} trên tổng số {task.total_pages} trang).")

            # 2. Render ảnh các trang
            for p_num in pages_to_process:
                if not ACTIVE_WORKERS.get(self.task_id, True):
                    self.emit_log(task, "Tiến trình đã bị dừng bởi người dùng.", "warning")
                    task.status = "cancelled"
                    self.db.commit()
                    return

                p_img_path = os.path.join(doc_dir, f"page_{p_num:04d}.png")
                if not os.path.exists(p_img_path):
                    if is_pdf:
                        PDFProcessor.render_page_to_image(
                            file_path, p_num, dpi=250, save_path=p_img_path,
                            enhance=merged_opts.get("enhance_scans", True)
                        )
                    else:
                        img = Image.open(file_path).convert("RGB")
                        if merged_opts.get("enhance_scans", True):
                            cv_img = ImagePreprocessor.pil_to_cv2(img)
                            cv_img = ImagePreprocessor.enhance_document_contrast(cv_img)
                            img = ImagePreprocessor.cv2_to_pil(cv_img)
                        img.save(p_img_path, "PNG")

            # 3. Xử lý các trang (OCR + Gemini Vision + AI Figure + 2-Column Split)
            configured_workers = int(sys_settings.get("concurrent_workers", 3))
            num_workers = max(1, min(len(api_keys), configured_workers, len(pages_to_process)))
            self.emit_log(task, f"⚡ Chạy bóc tách song song {num_workers} luồng với Gemini Vision ({model})...")

            completed_count = 0
            page_results = {}
            lock = threading.Lock()

            def process_single_page(p_num: int, worker_idx: int):
                if not ACTIVE_WORKERS.get(self.task_id, True):
                    return p_num, None

                page_img_path = os.path.join(doc_dir, f"page_{p_num:04d}.png")
                cached = cache_mgr.get_page_result(doc_dir, p_num)
                if cached:
                    self.emit_log(task, f"[Trang {p_num}] Lấy kết quả từ bộ nhớ đệm (cache)...")
                    p_text = cached.get("markdown", "")
                    p_figs = cached.get("figures", [])
                else:
                    page_img = Image.open(page_img_path).convert("RGB")

                    # Kiểm tra phát hiện bố cục 2 cột dọc (Two-Column Splitter)
                    is_2col = False
                    split_x = None
                    if merged_opts.get("auto_detect_columns", True):
                        cv_page = ImagePreprocessor.pil_to_cv2(page_img)
                        is_2col, split_x = ImagePreprocessor.detect_two_column_layout(cv_page)

                    if is_2col and split_x:
                        self.emit_log(task, f"[Trang {p_num}] 📖 Phát hiện bố cục 2 cột (vách ngăn x={split_x}). Bóc tách Nửa trái -> Nửa phải...")
                        col_l, col_r, split_x = ImagePreprocessor.split_two_columns(page_img, split_x)
                        resp_l = engine.process_page_image(col_l, p_num, preferred_key_idx=worker_idx)
                        resp_r = engine.process_page_image(col_r, p_num, preferred_key_idx=worker_idx)

                        md_l = resp_l.get("markdown", "").strip()
                        md_r = resp_r.get("markdown", "").strip()
                        figs_l = resp_l.get("figures", [])
                        figs_r = resp_r.get("figures", [])

                        w_full, h_full = page_img.size
                        w_l = split_x + 10
                        x_r_start = max(0, split_x - 10)
                        w_r = w_full - x_r_start

                        raw_figs = []
                        for fig in figs_l:
                            ymin, xmin, ymax, xmax = fig.get("box_2d", [0, 0, 1000, 1000])
                            xmin_mapped = int((xmin / 1000.0) * w_l / w_full * 1000)
                            xmax_mapped = int((xmax / 1000.0) * w_l / w_full * 1000)
                            fig["box_2d"] = [ymin, max(0, xmin_mapped), ymax, min(1000, xmax_mapped)]
                            raw_figs.append(fig)

                        l_count = len(figs_l)
                        for r_idx, fig in enumerate(figs_r, 1):
                            old_id = fig.get("id", f"HINH_{r_idx}")
                            new_id = f"HINH_{l_count + r_idx}"
                            fig["id"] = new_id
                            md_r = md_r.replace(f"[{old_id}]", f"[{new_id}]")
                            ymin, xmin, ymax, xmax = fig.get("box_2d", [0, 0, 1000, 1000])
                            xmin_px = x_r_start + (xmin / 1000.0) * w_r
                            xmax_px = x_r_start + (xmax / 1000.0) * w_r
                            xmin_mapped = int((xmin_px / w_full) * 1000)
                            xmax_mapped = int((xmax_px / w_full) * 1000)
                            fig["box_2d"] = [ymin, max(0, xmin_mapped), ymax, min(1000, xmax_mapped)]
                            raw_figs.append(fig)

                        p_text = f"{md_l}\n\n{md_r}" if md_l and md_r else (md_l or md_r)
                    else:
                        resp_data = engine.process_page_image(page_img, p_num, preferred_key_idx=worker_idx)
                        p_text = resp_data.get("markdown", "")
                        raw_figs = resp_data.get("figures", [])

                    # Chuẩn hóa công thức toán Deep Math Sanitizer
                    if merged_opts.get("normalize_gemini", True):
                        p_text = LatexFormatter.normalize_gemini_markdown(p_text)

                    # Cắt hình ảnh và AI vẽ lại hình học
                    p_figs = []
                    if merged_opts.get("detect_and_insert_images", True):
                        for f_idx, fig in enumerate(raw_figs, 1):
                            fig_id = fig.get("id", f"HINH_{f_idx}")
                            box = fig.get("box_2d", [0, 0, 1000, 1000])
                            crop_filename = f"page_{p_num:04d}_{fig_id}.png"
                            crop_path = os.path.join(doc_dir, crop_filename)

                            crop_path, refined_box = ImageCropper.crop_figure(page_img, box, crop_path, auto_refine=True)
                            is_blank, reject_reason = ImageCropper.is_blank_or_noise(crop_path)

                            # AI vẽ lại hình học vector
                            if not is_blank and merged_opts.get("ai_geometry_redraw", True):
                                desc = fig.get("description", "")
                                from core.ai_figure_artist import AIGeometryArtist
                                if AIGeometryArtist.is_likely_geometry(desc, context_text=p_text):
                                    self.emit_log(task, f"[Trang {p_num}] 🎨 AI đang vẽ lại hình [{fig_id}] vector chuẩn Bộ GD&ĐT...")
                                    target_redraw = os.path.join(doc_dir, f"page_{p_num:04d}_{fig_id}_ai_redraw.png")
                                    rd_res = AIGeometryArtist.redraw_figure(
                                        image_path=crop_path,
                                        output_path=target_redraw,
                                        api_keys=api_keys,
                                        model=model,
                                        description=desc,
                                        context_text=p_text,
                                        timeout_seconds=30
                                    )
                                    if rd_res and os.path.exists(rd_res):
                                        crop_path = rd_res
                                        self.emit_log(task, f"[Trang {p_num}] ✅ Đã vẽ lại hình [{fig_id}] thành công (vector 300 DPI)!", "success")

                            if not is_blank:
                                p_figs.append({
                                    "id": fig_id,
                                    "box_2d": refined_box,
                                    "cropped_path": crop_path
                                })

                    cache_mgr.save_page_result(doc_dir, p_num, p_text, p_figs)

                return p_num, {
                    "page_num": p_num,
                    "markdown": p_text,
                    "figures": p_figs
                }

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {
                    executor.submit(process_single_page, p_num, idx % len(api_keys)): p_num
                    for idx, p_num in enumerate(pages_to_process)
                }
                for fut in as_completed(futures):
                    if not ACTIVE_WORKERS.get(self.task_id, True):
                        break
                    p_num, res = fut.result()
                    if res:
                        with lock:
                            page_results[p_num] = res
                            completed_count += 1
                            task.processed_pages = completed_count
                            task.progress = int(10 + (completed_count / len(pages_to_process)) * 75)
                            self.emit_log(task, f"✓ Hoàn thành trang {p_num} ({completed_count}/{len(pages_to_process)})")

            if not ACTIVE_WORKERS.get(self.task_id, True):
                task.status = "cancelled"
                self.db.commit()
                return

            # 4. Tạo tài liệu Word (.docx)
            self.emit_log(task, "📄 Đang tổng hợp nội dung và tạo file Word (.docx) chuẩn OMML...")
            task.progress = 90
            self.db.commit()

            compact_saver = merged_opts.get("compact_paper_saver", True)
            builder = WordBuilder(
                font_name="Times New Roman",
                font_size_pt=11.0 if compact_saver else 13.0,
                convert_to_omml=True,
                toggle_tex_mode=False,
                format_multiple_choice=merged_opts.get("format_multiple_choice", True),
                smart_layout=merged_opts.get("smart_layout", True),
                compact_paper_saver=compact_saver
            )

            sorted_pages = [page_results[p] for p in sorted(page_results.keys())]
            for p_data in sorted_pages:
                p_num = p_data["page_num"]
                p_text = p_data["markdown"]
                p_figs = p_data["figures"]
                img_map = {f["id"]: f["cropped_path"] for f in p_figs if "cropped_path" in f}
                builder.add_page_content(
                    page_num=p_num,
                    markdown_text=p_text,
                    image_map=img_map
                )

            # Lưu file docx
            base_filename = os.path.splitext(task.original_filename)[0]
            clean_filename = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in base_filename])
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"{clean_filename}_{timestamp_str}.docx"
            output_docx_path = os.path.join(OUTPUT_DIR, output_filename)

            builder.save(output_docx_path)

            task.output_docx_path = output_docx_path
            task.status = "completed"
            task.progress = 100
            task.completed_at = datetime.utcnow()
            self.emit_log(task, f"🎉 Chuyển đổi thành công {len(pages_to_process)} trang! File Word đã sẵn sàng tải về.", "success")
            self.db.commit()

        except Exception as e:
            logger.exception(f"Lỗi xử lý Task {self.task_id}: {e}")
            try:
                task = self.db.query(Task).filter(Task.id == self.task_id).first()
                if task:
                    task.status = "failed"
                    task.error_message = str(e)
                    self.emit_log(task, f"❌ Lỗi: {str(e)}", "error")
                    self.db.commit()
            except Exception:
                pass
        finally:
            ACTIVE_WORKERS.pop(self.task_id, None)
            self.db.close()


def submit_task(task_id: str):
    worker = TaskWorker(task_id)
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()


def cancel_task(task_id: str):
    if task_id in ACTIVE_WORKERS:
        ACTIVE_WORKERS[task_id] = False
