import os
import json
import time
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget, QLabel,
    QLineEdit, QPushButton, QFileDialog, QCheckBox, QTextEdit, QProgressBar,
    QMessageBox, QGroupBox, QSpinBox, QComboBox, QListWidget, QListWidgetItem,
    QSplitter, QRadioButton, QButtonGroup, QFrame, QScrollArea
)
from PyQt6.QtGui import QIcon, QFont, QColor, QDragEnterEvent, QDropEvent, QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from core.cache_manager import CacheManager
from core.pdf_processor import PDFProcessor
from core.gemini_engine import GeminiEngine
from core.image_cropper import ImageCropper
from core.latex_formatter import LatexFormatter
from core.word_builder import WordBuilder
from gui.log_viewer import LogViewer
from gui.review_dialog import ReviewDialog

CONFIG_FILE = "config.json"


class OCRWorker(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int, int, str)
    page_completed_signal = pyqtSignal(int, str, list)
    finished_signal = pyqtSignal(str, str, list, list, dict)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        file_path: str,
        pages_to_process: List[int],
        config: Dict[str, Any],
        cache_manager: CacheManager
    ):
        super().__init__()
        self.file_path = file_path
        self.pages_to_process = pages_to_process
        self.config = config
        self.cache_manager = cache_manager
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            doc_dir = self.cache_manager.get_document_cache_dir(self.file_path)
            api_keys = self.config.get("api_keys", [])
            model = self.config.get("model", "gemini-3.5-flash-lite")
            threshold = float(self.config.get("slow_threshold_seconds", 30.0))
            opts = self.config.get("options", {})
            
            configured_workers = int(self.config.get("concurrent_workers", len(api_keys) or 3))
            num_workers = max(1, min(len(api_keys) if api_keys else 1, configured_workers))
            total_pages = len(self.pages_to_process)
            num_workers = min(num_workers, total_pages)

            engine = GeminiEngine(
                api_keys=api_keys,
                model=model,
                slow_threshold_seconds=threshold,
                log_callback=lambda msg, lvl: self.log_signal.emit(msg, lvl)
            )

            self.log_signal.emit(
                f"🚀 Khởi động xử lý {total_pages} trang với {num_workers} luồng song song (Multi-Threading x{num_workers})...",
                "info"
            )

            # 1. Kết xuất nhanh trước ảnh các trang còn thiếu (Pre-render)
            for p_num in self.pages_to_process:
                if not self.is_running:
                    self.log_signal.emit("Tiến trình đã bị dừng bởi người dùng.", "warning")
                    return
                p_img_path = os.path.join(doc_dir, f"page_{p_num:04d}.png")
                if not os.path.exists(p_img_path):
                    if opts.get("enhance_scans", True):
                        self.log_signal.emit(f"[Trang {p_num}] Đang tẩy trắng nền & xoay thẳng trang (OpenCV)...", "info")
                    PDFProcessor.render_page_to_image(
                        self.file_path, p_num, dpi=250, save_path=p_img_path,
                        enhance=opts.get("enhance_scans", True)
                    )

            # 2. Xử lý song song các trang qua ThreadPoolExecutor
            completed_lock = threading.Lock()
            completed_count = 0
            page_results = {}

            def process_single_page(p_num: int, worker_idx: int):
                if not self.is_running:
                    return p_num, None

                page_img_path = os.path.join(doc_dir, f"page_{p_num:04d}.png")

                # Check cache first
                cached_data = self.cache_manager.get_page_result(doc_dir, p_num)
                if cached_data:
                    self.log_signal.emit(f"Trang {p_num} đã có trong bộ đệm (cache), tải kết quả...", "info")
                    p_text = cached_data.get("markdown", "")
                    p_figs = cached_data.get("figures", [])
                    for f in p_figs:
                        f["page_num"] = p_num
                        f["page_image_path"] = page_img_path
                        if "is_blank" not in f:
                            is_b, r_reason = ImageCropper.is_blank_or_noise(f.get("cropped_path", ""))
                            f["is_blank"] = is_b
                            f["reject_reason"] = r_reason
                            f["selected"] = not is_b
                        elif "selected" not in f:
                            f["selected"] = not f.get("is_blank", False)
                else:
                    if not os.path.exists(page_img_path):
                        if opts.get("enhance_scans", True):
                            self.log_signal.emit(f"[Trang {p_num}] Đang tẩy trắng nền & xoay thẳng trang (OpenCV)...", "info")
                        page_img = PDFProcessor.render_page_to_image(
                            self.file_path, p_num, dpi=250, save_path=page_img_path,
                            enhance=opts.get("enhance_scans", True)
                        )
                    else:
                        from PIL import Image
                        page_img = Image.open(page_img_path)

                    # Check for 2-column layout (Sách scan / Đề thi in 2 cột)
                    is_2col = False
                    split_x = None
                    if opts.get("auto_detect_columns", True):
                        from core.image_preprocessor import ImagePreprocessor
                        cv_page = ImagePreprocessor.pil_to_cv2(page_img)
                        is_2col, split_x = ImagePreprocessor.detect_two_column_layout(cv_page)

                    if is_2col and split_x:
                        self.log_signal.emit(
                            f"[Trang {p_num}] 📖 Phát hiện bố cục 2 cột (vách ngăn x={split_x}). Đang bóc tách Cột trái -> Cột phải...",
                            "info"
                        )
                        col_l, col_r, split_x = ImagePreprocessor.split_two_columns(page_img, split_x)
                        resp_l = engine.process_page_image(col_l, p_num, preferred_key_idx=worker_idx)
                        resp_r = engine.process_page_image(col_r, p_num, preferred_key_idx=worker_idx)

                        md_l = resp_l.get("markdown", "").strip()
                        md_r = resp_r.get("markdown", "").strip()
                        figs_l = resp_l.get("figures", [])
                        figs_r = resp_r.get("figures", [])

                        # Map bounding boxes from columns to full page (0..1000)
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
                        # Gửi tới Gemini với API Key ưu tiên theo luồng (Key Affinity)
                        resp_data = engine.process_page_image(page_img, p_num, preferred_key_idx=worker_idx)
                        p_text = resp_data.get("markdown", "")
                        raw_figs = resp_data.get("figures", [])

                    # Cắt các hình minh họa được phát hiện
                    p_figs = []
                    if opts.get("detect_and_insert_images", True):
                        for f_idx, fig in enumerate(raw_figs, 1):
                            fig_id = fig.get("id", f"HINH_{f_idx}")
                            box = fig.get("box_2d", [0, 0, 1000, 1000])
                            crop_filename = f"page_{p_num:04d}_{fig_id}.png"
                            crop_path = os.path.join(doc_dir, crop_filename)

                            crop_path, refined_box = ImageCropper.crop_figure(page_img, box, crop_path, auto_refine=True)
                            is_blank, reject_reason = ImageCropper.is_blank_or_noise(crop_path)
                            if is_blank:
                                self.log_signal.emit(f"[Trang {p_num}] 🗑 Đã lọc hình rác/trắng [{fig_id}] ({reject_reason})", "warning")

                            orig_path = crop_path
                            redraw_path = None

                            # Tự động AI vẽ lại hình học chuẩn trực diện nếu được bật
                            if not is_blank and opts.get("ai_geometry_redraw", True):
                                desc = fig.get("description", "")
                                from core.ai_figure_artist import AIGeometryArtist
                                if AIGeometryArtist.is_likely_geometry(desc, context_text=p_text):
                                    self.log_signal.emit(f"[Trang {p_num}] ✨ Đang dùng AI vẽ lại hình học [{fig_id}] chuẩn trực diện...", "info")
                                    target_redraw = os.path.join(doc_dir, f"page_{p_num:04d}_{fig_id}_ai_redraw.png")
                                    rd_res = AIGeometryArtist.redraw_figure(
                                        image_path=crop_path,
                                        output_path=target_redraw,
                                        api_keys=self.api_keys,
                                        model=self.model,
                                        description=desc,
                                        context_text=p_text,
                                        timeout_seconds=25
                                    )
                                    if rd_res and os.path.exists(rd_res):
                                        redraw_path = rd_res
                                        crop_path = rd_res
                                        self.log_signal.emit(f"[Trang {p_num}] ✅ Đã vẽ lại hình học [{fig_id}] thành công (vector 300 DPI)!", "success")

                            p_figs.append({
                                "id": fig_id,
                                "page_num": p_num,
                                "page_image_path": page_img_path,
                                "box_2d": refined_box,
                                "cropped_path": crop_path,
                                "original_path": orig_path,
                                "redraw_path": redraw_path,
                                "description": fig.get("description", ""),
                                "context_text": p_text[:400],
                                "display_num": 0,
                                "selected": not is_blank,
                                "is_blank": is_blank,
                                "reject_reason": reject_reason
                            })

                    # Lưu cache trang
                    self.cache_manager.save_page_result(doc_dir, p_num, {
                        "markdown": p_text,
                        "figures": p_figs
                    })

                # Chuẩn hóa công thức Toán LaTeX
                if opts.get("normalize_gemini", True):
                    p_text = LatexFormatter.clean_and_normalize(
                        p_text,
                        fix_vietnamese_math=opts.get("vietnamese_in_math", True),
                        fix_decimals=True
                    )

                return p_num, (p_text, p_figs)

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                future_to_page = {}
                for idx, p_num in enumerate(self.pages_to_process):
                    worker_idx = idx % len(api_keys) if api_keys else 0
                    fut = executor.submit(process_single_page, p_num, worker_idx)
                    future_to_page[fut] = p_num

                for future in as_completed(future_to_page):
                    if not self.is_running:
                        self.log_signal.emit("Tiến trình đã bị dừng bởi người dùng.", "warning")
                        executor.shutdown(wait=False, cancel_futures=True)
                        return

                    try:
                        p_num, res = future.result()
                        if res is None:
                            continue
                        p_text, p_figs = res
                        page_results[p_num] = (p_text, p_figs)

                        with completed_lock:
                            completed_count += 1
                            curr_done = completed_count

                        self.progress_signal.emit(
                            curr_done,
                            total_pages,
                            f"Đã hoàn thành trang {p_num} ({curr_done}/{total_pages})..."
                        )
                        self.page_completed_signal.emit(p_num, p_text, p_figs)

                    except Exception as page_err:
                        self.log_signal.emit(f"Lỗi khi xử lý trang: {str(page_err)}", "error")
                        raise page_err

            if not self.is_running:
                return

            # 3. Tái cấu trúc kết quả theo đúng thứ tự trang 1..N
            all_markdown = []
            all_figures = []
            per_page_image_maps = {}

            for p_num in self.pages_to_process:
                if p_num not in page_results:
                    continue
                p_text, p_figs = page_results[p_num]
                all_markdown.append(p_text)
                per_page_image_maps[p_num] = {}
                for fig in p_figs:
                    fig["display_num"] = len(all_figures) + 1
                    all_figures.append(fig)
                    if fig.get("selected", True):
                        per_page_image_maps[p_num][fig["id"]] = fig["cropped_path"]

            # Áp dụng chuẩn hóa McMix / SmartTest nếu người dùng bật
            if opts.get("mcmix_compat", False):
                from core.mcmix_formatter import MCMixFormatter
                full_raw_text = "\n\n".join(all_markdown)
                answers = MCMixFormatter.extract_answer_key(full_raw_text)
                if answers:
                    ans_preview = ", ".join([f"{k}:{v}" for k, v in list(answers.items())[:8]])
                    self.log_signal.emit(f"🎯 Đã tự động bóc tách bảng đáp án ({len(answers)} câu: {ans_preview}...), đang gắn vào đề thi...", "success")
                formatted_markdown = []
                for p_text in all_markdown:
                    f_text = MCMixFormatter.format_mcmix(
                        p_text,
                        auto_tag=True,
                        underline_correct=True,
                        known_answers=answers
                    )
                    formatted_markdown.append(f_text)
                all_markdown = formatted_markdown

            # 4. Tạo tài liệu Word (.docx)
            full_text = "\n\n".join(all_markdown)
            docx_path = ""
            base_name = os.path.splitext(os.path.basename(self.file_path))[0]
            out_dir = os.path.abspath("output")
            os.makedirs(out_dir, exist_ok=True)

            if opts.get("create_word", True):
                docx_path = os.path.join(out_dir, f"{base_name}_Converted.docx")

                wb = WordBuilder(
                    font_name="Times New Roman",
                    font_size_pt=13.0,
                    convert_to_omml=not opts.get("toggle_tex", False),
                    toggle_tex_mode=opts.get("toggle_tex", False),
                    format_multiple_choice=opts.get("format_multiple_choice", True),
                    smart_layout=opts.get("smart_layout", True)
                )
                first_page = all_markdown[0].strip() if all_markdown else ""
                if not (first_page.startswith("|") or first_page.startswith("#")):
                    wb.add_header_title(f"TÀI LIỆU TOÁN HỌC: {base_name.upper()}")

                for idx, p_num in enumerate(self.pages_to_process):
                    p_text = all_markdown[idx]
                    wb.add_page_content(p_num, p_text, per_page_image_maps.get(p_num, {}))
                    if idx < len(self.pages_to_process) - 1:
                        wb.doc.add_page_break()

                try:
                    wb.save(docx_path)
                except PermissionError:
                    docx_path = os.path.join(out_dir, f"{base_name}_Converted_{time.strftime('%H%M%S')}.docx")
                    wb.save(docx_path)

                self.log_signal.emit(f"Đã tạo file Word thành công tại: {docx_path}", "success")

            # 5. Xuất song song file LaTeX (.tex) cho TeXmaker / Overleaf
            tex_path = ""
            if opts.get("export_tex", False):
                from core.latex_exporter import LatexExporter
                tex_path = LatexExporter.export_to_tex(
                    base_name=base_name,
                    all_markdown_pages=all_markdown,
                    per_page_image_maps=per_page_image_maps,
                    output_dir=out_dir
                )
                self.log_signal.emit(f"Đã xuất file LaTeX (.tex) chuẩn TeXmaker / Overleaf: {tex_path}", "success")

            self.finished_signal.emit(docx_path, full_text, all_figures, all_markdown, per_page_image_maps)

        except Exception as e:
            self.error_signal.emit(str(e))
            self.log_signal.emit(f"Lỗi: {str(e)}", "error")



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chuyển PDF/Ảnh sang Word MathType & OMML")
        self.resize(1180, 820)
        self.setAcceptDrops(True)

        self.cache_manager = CacheManager()
        self.log_viewer = LogViewer(self)
        self.log_viewer.stop_requested.connect(self._stop_processing)

        self.current_figures = []
        self.last_docx_path = ""
        self.last_tex_path = ""
        self.last_file_path = ""
        self.last_markdown_pages = []
        self.last_pages_processed = []
        self.worker = None

        # Side-by-Side Visual Diff Preview state
        self.processed_pages_data = {}  # {p_num: {"image_path": str, "markdown": str, "figures": list}}
        self.preview_page_list = []
        self.current_preview_page_idx = 0

        self._load_config()
        self._init_ui()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception:
                self.config = {}
        elif os.path.exists("config.example.json"):
            try:
                with open("config.example.json", "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception:
                self.config = {}
        else:
            self.config = {}

    def _save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # Header Banner
        header = QLabel("CHUYỂN ẢNH / PDF SÁCH TOÁN - KHTN THÀNH WORD CÔNG THỨC MATHTYPE")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #005a9e, stop:1 #0078d4);
            color: white;
            font-size: 15px;
            font-weight: bold;
            padding: 10px;
            border-radius: 6px;
        """)
        main_layout.addWidget(header)

        # Quick action links (Step 1, Step 2, HDSD, Log)
        links_layout = QHBoxLayout()
        links_layout.setSpacing(8)

        btn_api_lib = QPushButton("🔑 Bc 1: Cấu hình API Keys")
        btn_api_lib.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                font-weight: bold;
                padding: 5px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #e0a800; }
        """)
        btn_api_lib.clicked.connect(lambda: self.tabs.setCurrentIndex(2))
        links_layout.addWidget(btn_api_lib)

        btn_ai_studio = QPushButton("🌐 Bc 2: Lấy Key Google AI Studio")
        btn_ai_studio.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                padding: 5px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #138496; }
        """)
        btn_ai_studio.clicked.connect(lambda: os.system("start https://aistudio.google.com/app/apikey"))
        links_layout.addWidget(btn_ai_studio)

        btn_guide = QPushButton("📖 Hướng dẫn sử dụng")
        btn_guide.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 5px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        btn_guide.clicked.connect(self._open_guide_dialog)
        links_layout.addWidget(btn_guide)

        links_layout.addStretch()

        self.btn_show_log = QPushButton("📜 Nhật ký tiến trình (Log)")
        self.btn_show_log.setStyleSheet("""
            QPushButton {
                background-color: #343a40;
                color: #38bdf8;
                font-weight: bold;
                padding: 5px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #23272b; }
        """)
        self.btn_show_log.clicked.connect(self.log_viewer.show)
        links_layout.addWidget(self.btn_show_log)

        main_layout.addLayout(links_layout)

        # Main Tabs
        self.tabs = QTabWidget()
        self.tab_convert = QWidget()
        self.tab_splitter = QWidget()
        self.tab_config = QWidget()

        self.tabs.addTab(self.tab_convert, "📄 Ảnh, PDF -> WORD")
        self.tabs.addTab(self.tab_splitter, "✂ Chia nhỏ PDF (Sách 400 trang)")
        self.tabs.addTab(self.tab_config, "⚙ Quản lý 3 API Keys")

        self._setup_convert_tab()
        self._setup_splitter_tab()
        self._setup_config_tab()

        main_layout.addWidget(self.tabs)

    def _setup_convert_tab(self):
        layout = QVBoxLayout(self.tab_convert)
        layout.setSpacing(8)

        # File Selection & Drag-and-drop Card
        top_group = QGroupBox("1. Chọn tài liệu PDF scan hoặc File Ảnh")
        top_layout = QVBoxLayout(top_group)

        # Drag and Drop Banner Box
        self.drop_banner = QFrame()
        self.drop_banner.setFrameShape(QFrame.Shape.StyledPanel)
        self.drop_banner.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 2px dashed #0078d4;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        banner_layout = QHBoxLayout(self.drop_banner)
        self.lbl_drop_text = QLabel("📥 KÉO & THẢ FILE PDF HOẶC ẢNH VÀO ĐÂY (hoặc bấm nút Chọn File)")
        self.lbl_drop_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_drop_text.setStyleSheet("font-size: 13px; font-weight: bold; color: #005a9e;")
        banner_layout.addWidget(self.lbl_drop_text)

        btn_browse_banner = QPushButton("📂 Chọn File...")
        btn_browse_banner.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                padding: 6px 18px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #005a9e; }
        """)
        btn_browse_banner.clicked.connect(self._browse_file)
        banner_layout.addWidget(btn_browse_banner)
        top_layout.addWidget(self.drop_banner)

        # Path line edit
        file_h = QHBoxLayout()
        self.txt_file_path = QLineEdit()
        self.txt_file_path.setPlaceholderText("Đường dẫn file PDF hoặc Ảnh sẽ hiển thị tại đây...")
        file_h.addWidget(self.txt_file_path)

        btn_browse = QPushButton("Duyệt...")
        btn_browse.clicked.connect(self._browse_file)
        file_h.addWidget(btn_browse)
        top_layout.addLayout(file_h)

        # Page range selection
        range_h = QHBoxLayout()
        self.radio_all_pages = QRadioButton("Toàn bộ file (Chưa chọn file)")
        self.radio_all_pages.setChecked(True)
        self.radio_custom_pages = QRadioButton("Chọn dải trang:")

        self.bg_pages = QButtonGroup()
        self.bg_pages.addButton(self.radio_all_pages)
        self.bg_pages.addButton(self.radio_custom_pages)

        self.txt_page_range = QLineEdit()
        self.txt_page_range.setPlaceholderText("Ví dụ: 1-4 hoặc 1-15, 20, 25-40")
        self.txt_page_range.setEnabled(False)
        self.radio_custom_pages.toggled.connect(lambda v: self.txt_page_range.setEnabled(v))

        range_h.addWidget(self.radio_all_pages)
        range_h.addWidget(self.radio_custom_pages)
        range_h.addWidget(self.txt_page_range)
        range_h.addStretch()
        top_layout.addLayout(range_h)

        layout.addWidget(top_group)

        # Options check boxes (matching ToolMathpix)
        opts_group = QGroupBox("2. Tùy chọn xử lý MathType & Hình ảnh")
        opts_layout = QHBoxLayout(opts_group)

        opts = self.config.get("options", {})
        col1 = QVBoxLayout()
        self.chk_create_word = QCheckBox("Tạo file Word (.docx) khi hoàn tất")
        self.chk_create_word.setChecked(opts.get("create_word", True))
        self.chk_normalize_gemini = QCheckBox("Chuẩn hóa công thức Toán & MathType")
        self.chk_normalize_gemini.setChecked(opts.get("normalize_gemini", True))
        self.chk_toggle_tex = QCheckBox("Tự động mở Toggle TeX khi mở Word")
        self.chk_toggle_tex.setChecked(opts.get("toggle_tex", False))
        self.chk_enhance_scans = QCheckBox("Tẩy trắng nền, khử bóng đen & xoay thẳng trang (OpenCV)")
        self.chk_enhance_scans.setChecked(opts.get("enhance_scans", True))
        self.chk_auto_columns = QCheckBox("Tự động bóc tách trang in 2 cột (Sách scan / Đề thi 2 cột)")
        self.chk_auto_columns.setChecked(opts.get("auto_detect_columns", True))
        self.chk_export_tex = QCheckBox("Xuất song song file LaTeX (.tex) cho TeXmaker / Overleaf")
        self.chk_export_tex.setChecked(opts.get("export_tex", False))
        col1.addWidget(self.chk_create_word)
        col1.addWidget(self.chk_normalize_gemini)
        col1.addWidget(self.chk_toggle_tex)
        col1.addWidget(self.chk_enhance_scans)
        col1.addWidget(self.chk_auto_columns)
        col1.addWidget(self.chk_export_tex)

        col2 = QVBoxLayout()
        self.chk_vietnamese_math = QCheckBox("Chữ Việt trong công thức (\\text{...})")
        self.chk_vietnamese_math.setChecked(opts.get("vietnamese_in_math", True))
        self.chk_decorate_word = QCheckBox("Trang trí Word chuẩn Bộ GD (Times New Roman 13pt, 2cm)")
        self.chk_decorate_word.setChecked(opts.get("decorate_word", True))
        self.chk_detect_images = QCheckBox("Tự động nhận diện và cắt hình minh họa vào Word")
        self.chk_detect_images.setChecked(opts.get("detect_and_insert_images", True))
        self.chk_smart_layout = QCheckBox("Bố cục thông minh: Đặt hình bên phải câu hỏi (Smart Fluid Layout)")
        self.chk_smart_layout.setChecked(opts.get("smart_layout", True))
        self.chk_format_mc = QCheckBox("Dàn trang trắc nghiệm 4 cột / 2 cột tự động (Chuẩn BGD)")
        self.chk_format_mc.setChecked(opts.get("format_multiple_choice", True))
        self.chk_mcmix = QCheckBox("Trộn đề McMix, SmartTest (Tag [NB], gạch chân đáp án)")
        self.chk_mcmix.setChecked(opts.get("mcmix_compat", False))
        col2.addWidget(self.chk_vietnamese_math)
        col2.addWidget(self.chk_decorate_word)
        col2.addWidget(self.chk_detect_images)
        self.chk_ai_redraw = QCheckBox("✨ Tự động vẽ lại hình học trực diện & siêu nét (AI Geometry Artist)")
        self.chk_ai_redraw.setChecked(opts.get("ai_geometry_redraw", True))
        col2.addWidget(self.chk_ai_redraw)
        col2.addWidget(self.chk_smart_layout)
        col2.addWidget(self.chk_format_mc)
        col2.addWidget(self.chk_mcmix)

        opts_layout.addLayout(col1)
        opts_layout.addLayout(col2)
        layout.addWidget(opts_group)

        # Big Send Action Button
        self.btn_send = QPushButton("🚀 GỬI YÊU CẦU XỬ LÝ (CHUYỂN SANG WORD)")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d92525, stop:1 #e02424);
                color: white;
                font-size: 15px;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #b91c1c;
            }
            QPushButton:disabled {
                background: #9ca3af;
                color: #e5e7eb;
            }
        """)
        self.btn_send.clicked.connect(self._start_conversion)
        layout.addWidget(self.btn_send)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                height: 24px;
                text-align: center;
                font-weight: bold;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background-color: #f6f8fa;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 3. Side-by-Side Visual Diff Splitter (Khung đối chiếu song song: Scan gốc vs Văn bản bóc tách)
        self.preview_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.preview_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #cbd5e1;
                width: 5px;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #0078d4;
            }
        """)

        # LEFT PANEL: Original Scanned Page Preview
        left_panel = QWidget()
        left_vbox = QVBoxLayout(left_panel)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(4)

        # Left header bar: Page navigator
        left_bar = QHBoxLayout()
        left_bar.setContentsMargins(4, 2, 4, 2)
        lbl_left_title = QLabel("📄 <b>Trang scan gốc:</b>")
        lbl_left_title.setStyleSheet("color: #0f172a; font-size: 12px;")
        left_bar.addWidget(lbl_left_title)

        self.btn_prev_page = QPushButton("◀")
        self.btn_prev_page.setFixedWidth(28)
        self.btn_prev_page.setToolTip("Trang trước")
        self.btn_prev_page.clicked.connect(self._prev_preview_page)
        self.btn_prev_page.setEnabled(False)
        left_bar.addWidget(self.btn_prev_page)

        self.lbl_page_counter = QLabel("0 / 0")
        self.lbl_page_counter.setStyleSheet("font-weight: bold; color: #1e40af; font-size: 12px;")
        left_bar.addWidget(self.lbl_page_counter)

        self.btn_next_page = QPushButton("▶")
        self.btn_next_page.setFixedWidth(28)
        self.btn_next_page.setToolTip("Trang tiếp")
        self.btn_next_page.clicked.connect(self._next_preview_page)
        self.btn_next_page.setEnabled(False)
        left_bar.addWidget(self.btn_next_page)

        left_bar.addStretch()

        self.btn_fit_page = QPushButton("🔍 Vừa khung")
        self.btn_fit_page.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.btn_fit_page.clicked.connect(self._fit_preview_image)
        left_bar.addWidget(self.btn_fit_page)

        left_vbox.addLayout(left_bar)

        # Scroll area for page image
        self.scroll_page_preview = QScrollArea()
        self.scroll_page_preview.setWidgetResizable(True)
        self.scroll_page_preview.setStyleSheet("background-color: #f8fafc; border: 1px solid #d0d7de; border-radius: 4px;")
        self.lbl_page_image = QLabel("Chưa có trang scan nào để xem trước.\nNhấn 'GỬI YÊU CẦU XỬ LÝ' để bắt đầu số hóa.")
        self.lbl_page_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_page_image.setStyleSheet("color: #64748b; font-size: 13px; font-style: italic;")
        self.scroll_page_preview.setWidget(self.lbl_page_image)
        left_vbox.addWidget(self.scroll_page_preview)

        # RIGHT PANEL: Recognized Markdown & LaTeX
        right_panel = QWidget()
        right_vbox = QVBoxLayout(right_panel)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(4)

        right_bar = QHBoxLayout()
        right_bar.setContentsMargins(4, 2, 4, 2)
        lbl_right_title = QLabel("📝 <b>Văn bản & Công thức bóc tách:</b>")
        lbl_right_title.setStyleSheet("color: #0f172a; font-size: 12px;")
        right_bar.addWidget(lbl_right_title)

        right_bar.addStretch()

        self.btn_view_mode_page = QPushButton("Trang đang chọn")
        self.btn_view_mode_page.setCheckable(True)
        self.btn_view_mode_page.setChecked(True)
        self.btn_view_mode_page.setStyleSheet("font-size: 11px; padding: 2px 8px;")

        self.btn_view_mode_all = QPushButton("Toàn bộ tài liệu")
        self.btn_view_mode_all.setCheckable(True)
        self.btn_view_mode_all.setStyleSheet("font-size: 11px; padding: 2px 8px;")

        self.bg_view_mode = QButtonGroup()
        self.bg_view_mode.addButton(self.btn_view_mode_page)
        self.bg_view_mode.addButton(self.btn_view_mode_all)
        self.btn_view_mode_page.toggled.connect(self._on_view_mode_changed)

        right_bar.addWidget(self.btn_view_mode_page)
        right_bar.addWidget(self.btn_view_mode_all)

        right_vbox.addLayout(right_bar)

        self.txt_result = QTextEdit()
        self.txt_result.setPlaceholderText("Kết quả văn bản bóc tách và công thức LaTeX sẽ hiển thị trực tiếp tại đây...")
        self.txt_result.setStyleSheet("font-family: 'Consolas', 'Times New Roman'; font-size: 13px; border: 1px solid #d0d7de; border-radius: 4px;")
        right_vbox.addWidget(self.txt_result)

        self.preview_splitter.addWidget(left_panel)
        self.preview_splitter.addWidget(right_panel)
        self.preview_splitter.setSizes([450, 550])

        layout.addWidget(self.preview_splitter)

        # Bottom Action Bar
        bottom_h = QHBoxLayout()
        bottom_h.setSpacing(10)

        self.btn_open_word = QPushButton("📄 Mở file Word")
        self.btn_open_word.setEnabled(False)
        self.btn_open_word.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #005a9e; }
            QPushButton:disabled { background-color: #d1d5db; color: #9ca3af; }
        """)
        self.btn_open_word.clicked.connect(self._open_word_file)
        bottom_h.addWidget(self.btn_open_word)

        self.btn_open_tex = QPushButton("📑 Mở file LaTeX (.tex)")
        self.btn_open_tex.setEnabled(False)
        self.btn_open_tex.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #6d28d9; }
            QPushButton:disabled { background-color: #d1d5db; color: #9ca3af; }
        """)
        self.btn_open_tex.clicked.connect(self._open_tex_file)
        bottom_h.addWidget(self.btn_open_tex)

        self.btn_open_output = QPushButton("📂 Mở thư mục kết quả")
        self.btn_open_output.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #138496; }
        """)
        self.btn_open_output.clicked.connect(self._open_output_folder)
        bottom_h.addWidget(self.btn_open_output)

        self.btn_review_images = QPushButton("🖼 Xem lại & chỉnh hình ảnh")
        self.btn_review_images.setEnabled(False)
        self.btn_review_images.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #d1d5db; color: #9ca3af; }
        """)
        self.btn_review_images.clicked.connect(self._show_review_dialog)
        bottom_h.addWidget(self.btn_review_images)

        self.btn_copy = QPushButton("📋 Copy nội dung")
        self.btn_copy.setStyleSheet("padding: 8px 14px; font-weight: bold;")
        self.btn_copy.clicked.connect(lambda: self.txt_result.selectAll() or self.txt_result.copy())
        bottom_h.addWidget(self.btn_copy)

        self.btn_copy_tex = QPushButton("📋 Sao chép mã TeX (MathType Alt+\\)")
        self.btn_copy_tex.setToolTip("Sao chép toàn bộ văn bản và công thức LaTeX để dán vào Word, sau đó bấm Alt + \\ để chuyển thành MathType tức thì.")
        self.btn_copy_tex.setStyleSheet("""
            QPushButton {
                background-color: #4b5563;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #374151; }
        """)
        self.btn_copy_tex.clicked.connect(self._copy_tex_code)
        bottom_h.addWidget(self.btn_copy_tex)

        bottom_h.addStretch()

        layout.addLayout(bottom_h)

    def _setup_splitter_tab(self):
        layout = QVBoxLayout(self.tab_splitter)

        intro = QLabel(
            "<b style='color: #0369a1; font-size: 14px;'>CÔNG CỤ TỰ ĐỘNG CHIA NHỎ PDF SÁCH 400 TRANG:</b><br>"
            "<span style='color: #0f172a; font-size: 13px;'>Cắt nhỏ file PDF scan thành các phần 20 - 50 trang giúp chống đơ Word, không tràn RAM và dễ dàng rà soát từng chương.</span>"
        )
        intro.setStyleSheet("""
            QLabel {
                background-color: #e0f2fe;
                color: #0f172a;
                border: 1px solid #7dd3fc;
                padding: 12px;
                border-radius: 6px;
            }
        """)
        layout.addWidget(intro)

        split_group = QGroupBox("Chọn PDF và cài đặt chia")
        split_layout = QVBoxLayout(split_group)

        f_h = QHBoxLayout()
        self.txt_split_file = QLineEdit()
        self.txt_split_file.setPlaceholderText("Chọn file PDF cần chia...")
        f_h.addWidget(self.txt_split_file)

        btn_browse_split = QPushButton("📂 Chọn PDF...")
        btn_browse_split.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 18px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #005a9e; }
        """)
        btn_browse_split.clicked.connect(self._browse_split_pdf)
        f_h.addWidget(btn_browse_split)
        split_layout.addLayout(f_h)

        info_h = QHBoxLayout()
        self.lbl_pdf_info = QLabel("Tổng số trang: Chưa chọn file")
        self.lbl_pdf_info.setStyleSheet("font-weight: bold; color: #0284c7; font-size: 13px;")
        info_h.addWidget(self.lbl_pdf_info)

        info_h.addStretch()

        lbl_chunk = QLabel("Số trang mỗi phần:")
        lbl_chunk.setStyleSheet("font-weight: bold;")
        info_h.addWidget(lbl_chunk)
        self.spin_chunk_size = QSpinBox()
        self.spin_chunk_size.setRange(5, 200)
        self.spin_chunk_size.setValue(30)
        info_h.addWidget(self.spin_chunk_size)
        split_layout.addLayout(info_h)

        btn_do_split = QPushButton("✂ TIẾN HÀNH CHIA NHỎ PDF NGAY")
        btn_do_split.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        btn_do_split.clicked.connect(self._do_split_pdf)
        split_layout.addWidget(btn_do_split)

        layout.addWidget(split_group)

        self.list_split_results = QListWidget()
        layout.addWidget(QLabel("Danh sách các file PDF đã chia:"))
        layout.addWidget(self.list_split_results)

        btn_open_folder = QPushButton("📂 Mở thư mục chứa file đã chia")
        btn_open_folder.clicked.connect(lambda: subprocess.Popen(f'explorer "{os.path.abspath("output/split_pdf")}"'))
        layout.addWidget(btn_open_folder)

    def _setup_config_tab(self):
        layout = QVBoxLayout(self.tab_config)

        # Gemini API Keys
        key_group = QGroupBox("Danh sách Google Gemini API Keys (Xoay tua Round-Robin tự động)")
        key_layout = QVBoxLayout(key_group)

        self.list_keys = QListWidget()
        for k in self.config.get("api_keys", []):
            self.list_keys.addItem(k)
        key_layout.addWidget(self.list_keys)

        add_h = QHBoxLayout()
        self.txt_new_key = QLineEdit()
        self.txt_new_key.setPlaceholderText("Nhập API Key mới (bắt đầu bằng AQ... hoặc AIza...)")
        add_h.addWidget(self.txt_new_key)

        btn_add_key = QPushButton("➕ Thêm Key")
        btn_add_key.clicked.connect(self._add_key)
        add_h.addWidget(btn_add_key)

        btn_del_key = QPushButton("🗑 Xóa Key")
        btn_del_key.clicked.connect(self._del_key)
        add_h.addWidget(btn_del_key)
        key_layout.addLayout(add_h)

        layout.addWidget(key_group)

        # Model & threshold & Multi-Workers
        model_group = QGroupBox("Cấu hình Tăng tốc Xử lý & Model AI")
        m_layout = QGridLayout(model_group)
        m_layout.setContentsMargins(15, 15, 15, 15)
        m_layout.setHorizontalSpacing(15)
        m_layout.setVerticalSpacing(10)

        m_layout.addWidget(QLabel("Model Gemini:"), 0, 0)
        self.cb_model = QComboBox()
        self.cb_model.addItems(["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-flash-latest"])
        self.cb_model.setCurrentText(self.config.get("model", "gemini-3.5-flash-lite"))
        m_layout.addWidget(self.cb_model, 0, 1)

        m_layout.addWidget(QLabel("Số luồng chạy song song (Multi-Workers):"), 0, 2)
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 10)
        self.spin_workers.setValue(int(self.config.get("concurrent_workers", len(self.config.get("api_keys", [])) or 3)))
        self.spin_workers.setToolTip("Khuyên dùng: Bằng số API Key bạn có (ví dụ 3 Key = 3 luồng) để tăng tốc độ xử lý gấp 3 lần.")
        m_layout.addWidget(self.spin_workers, 0, 3)

        m_layout.addWidget(QLabel("Ngưỡng trễ đổi Key (giây):"), 1, 0)
        self.spin_threshold = QSpinBox()
        self.spin_threshold.setRange(5, 60)
        self.spin_threshold.setValue(int(self.config.get("slow_threshold_seconds", 30)))
        m_layout.addWidget(self.spin_threshold, 1, 1)

        lbl_hint = QLabel("⚡ <i>Mẹo tăng tốc: Chạy 3 luồng song song trên 3 API Key giúp xử lý 4 trang sách trong ~10-15 giây thay vì 45 giây!</i>")
        lbl_hint.setStyleSheet("color: #0078d4; font-size: 11px;")
        m_layout.addWidget(lbl_hint, 1, 2, 1, 2)

        layout.addWidget(model_group)

        btn_save_cfg = QPushButton("💾 LƯU CẤU HÌNH VÀO FILE")
        btn_save_cfg.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold; padding: 10px;")
        btn_save_cfg.clicked.connect(self._save_config_from_ui)
        layout.addWidget(btn_save_cfg)

        layout.addStretch()

    # Drag and Drop handlers
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for u in urls:
                fpath = u.toLocalFile()
                if fpath.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for u in event.mimeData().urls():
                fpath = u.toLocalFile()
                if fpath.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                    self._set_selected_file(fpath)
                    event.acceptProposedAction()
                    break

    def _set_selected_file(self, fpath: str):
        self.txt_file_path.setText(fpath)
        base_name = os.path.basename(fpath)
        if fpath.lower().endswith(".pdf"):
            try:
                count = PDFProcessor.get_page_count(fpath)
                self.radio_all_pages.setText(f"Toàn bộ file ({count} trang)")
                self.lbl_drop_text.setText(f"✔ ĐÃ CHỌN: {base_name} ({count} trang) — Sẵn sàng chuyển đổi!")
            except Exception:
                self.lbl_drop_text.setText(f"✔ ĐÃ CHỌN: {base_name}")
        else:
            self.radio_all_pages.setText("Toàn bộ file (1 ảnh)")
            self.lbl_drop_text.setText(f"✔ ĐÃ CHỌN: {base_name} (1 ảnh)")
        self.tabs.setCurrentIndex(0)

    def _browse_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn tài liệu", "", "PDF & Ảnh (*.pdf *.png *.jpg *.jpeg)")
        if f:
            self._set_selected_file(f)

    def _open_guide_dialog(self):
        msg = (
            "<h3>HƯỚNG DẪN SỬ DỤNG NHANH</h3>"
            "<ol>"
            "<li><b>Chọn file:</b> Kéo thả file PDF hoặc Ảnh vào khung, hoặc bấm nút 'Chọn File'.</li>"
            "<li><b>Chọn trang:</b> Chọn 'Toàn bộ file' hoặc gõ dải trang muốn làm (ví dụ 1-4).</li>"
            "<li><b>Bắt đầu:</b> Bấm nút màu đỏ <b>'GỬI YÊU CẦU XỬ LÝ'</b>. Hệ thống tự động xoay tua 3 API key và chuyển đổi sang Word.</li>"
            "<li><b>Xem lại hình:</b> Nếu bài có hình học/minh họa, bạn có thể bấm <b>'Xem lại & chỉnh hình ảnh'</b> để bật/tắt hình hoặc sửa khung cắt.</li>"
            "<li><b>Mở Word:</b> Bấm <b>'Mở file Word'</b> để xem kết quả. Các công thức toán đã là OMML chuẩn MathType.</li>"
            "</ol>"
            "<p><i>Lưu ý: Với sách scan dài ~400 trang, bạn có thể dùng tab <b>'Chia nhỏ PDF'</b> để chia thành từng phần 30 trang giúp máy xử lý nhanh và an toàn nhất!</i></p>"
        )
        QMessageBox.information(self, "Hướng dẫn sử dụng", msg)

    def _browse_split_pdf(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn file PDF lớn", "", "PDF Files (*.pdf)")
        if f:
            self.txt_split_file.setText(f)
            count = PDFProcessor.get_page_count(f)
            self.lbl_pdf_info.setText(f"Tổng số trang: {count} trang")

    def _do_split_pdf(self):
        pdf_path = self.txt_split_file.text().strip()
        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file PDF hợp lệ!")
            return

        chunk = self.spin_chunk_size.value()
        out_dir = os.path.abspath("output/split_pdf")
        created = PDFProcessor.split_pdf(pdf_path, out_dir, chunk)

        self.list_split_results.clear()
        for c in created:
            self.list_split_results.addItem(os.path.basename(c))

        QMessageBox.information(self, "Thành công", f"Đã chia thành {len(created)} file PDF nhỏ trong thư mục output/split_pdf!")

    def _add_key(self):
        k = self.txt_new_key.text().strip()
        if k:
            self.list_keys.addItem(k)
            self.txt_new_key.clear()

    def _del_key(self):
        item = self.list_keys.currentItem()
        if item:
            self.list_keys.takeItem(self.list_keys.row(item))

    def _save_config_from_ui(self):
        keys = [self.list_keys.item(i).text() for i in range(self.list_keys.count())]
        self.config["api_keys"] = keys
        self.config["model"] = self.cb_model.currentText()
        self.config["slow_threshold_seconds"] = self.spin_threshold.value()
        self.config["concurrent_workers"] = self.spin_workers.value()
        self.config["options"] = {
            "create_word": self.chk_create_word.isChecked(),
            "normalize_gemini": self.chk_normalize_gemini.isChecked(),
            "toggle_tex": self.chk_toggle_tex.isChecked(),
            "vietnamese_in_math": self.chk_vietnamese_math.isChecked(),
            "decorate_word": self.chk_decorate_word.isChecked(),
            "detect_and_insert_images": self.chk_detect_images.isChecked(),
            "ai_geometry_redraw": self.chk_ai_redraw.isChecked(),
            "smart_layout": self.chk_smart_layout.isChecked(),
            "format_multiple_choice": self.chk_format_mc.isChecked(),
            "enhance_scans": self.chk_enhance_scans.isChecked(),
            "auto_detect_columns": self.chk_auto_columns.isChecked(),
            "export_tex": self.chk_export_tex.isChecked(),
            "mcmix_compat": self.chk_mcmix.isChecked()
        }
        self._save_config()
        QMessageBox.information(self, "Thành công", "Đã lưu cấu hình thành công!")

    def _start_conversion(self):
        file_path = self.txt_file_path.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file PDF hoặc Ảnh trước!")
            return

        keys = self.config.get("api_keys", [])
        if not keys:
            QMessageBox.warning(self, "Thiếu API Key", "Vui lòng thêm ít nhất 1 Gemini API Key trong tab Cấu hình!")
            return

        # Determine pages
        if file_path.lower().endswith(".pdf"):
            total_pages = PDFProcessor.get_page_count(file_path)
            if self.radio_all_pages.isChecked():
                pages = list(range(1, total_pages + 1))
            else:
                pages = PDFProcessor.parse_page_ranges(self.txt_page_range.text(), total_pages)
        else:
            pages = [1]

        self.last_file_path = file_path
        self.last_pages_processed = pages
        self.btn_send.setEnabled(False)
        self.btn_open_word.setEnabled(False)
        self.btn_open_tex.setEnabled(False)
        self.btn_review_images.setEnabled(False)
        self.txt_result.clear()
        self.current_figures.clear()

        # Reset visual diff preview
        self.processed_pages_data.clear()
        self.preview_page_list.clear()
        self.current_preview_page_idx = 0
        self._update_preview_display()

        # Show Log Viewer
        self.log_viewer.clear_logs()
        self.log_viewer.show()

        # Update options in config
        self.config["options"] = {
            "create_word": self.chk_create_word.isChecked(),
            "normalize_gemini": self.chk_normalize_gemini.isChecked(),
            "toggle_tex": self.chk_toggle_tex.isChecked(),
            "vietnamese_in_math": self.chk_vietnamese_math.isChecked(),
            "decorate_word": self.chk_decorate_word.isChecked(),
            "detect_and_insert_images": self.chk_detect_images.isChecked(),
            "ai_geometry_redraw": self.chk_ai_redraw.isChecked(),
            "smart_layout": self.chk_smart_layout.isChecked(),
            "format_multiple_choice": self.chk_format_mc.isChecked(),
            "enhance_scans": self.chk_enhance_scans.isChecked(),
            "auto_detect_columns": self.chk_auto_columns.isChecked(),
            "export_tex": self.chk_export_tex.isChecked(),
            "mcmix_compat": self.chk_mcmix.isChecked()
        }

        self.worker = OCRWorker(file_path, pages, self.config, self.cache_manager)
        self.worker.log_signal.connect(self.log_viewer.append_log)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.page_completed_signal.connect(self._on_page_completed)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _stop_processing(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()

    def _on_progress(self, current: int, total: int, text: str):
        pct = int((current / total) * 100)
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"{text} ({pct}%)")

    def _prev_preview_page(self):
        if self.preview_page_list and self.current_preview_page_idx > 0:
            self.current_preview_page_idx -= 1
            self._update_preview_display()

    def _next_preview_page(self):
        if self.preview_page_list and self.current_preview_page_idx < len(self.preview_page_list) - 1:
            self.current_preview_page_idx += 1
            self._update_preview_display()

    def _on_view_mode_changed(self):
        self._update_preview_display()

    def _fit_preview_image(self):
        self._update_preview_display()

    def _update_preview_display(self):
        if not hasattr(self, 'lbl_page_counter') or not hasattr(self, 'lbl_page_image'):
            return

        if not self.preview_page_list:
            self.lbl_page_counter.setText("0 / 0")
            self.btn_prev_page.setEnabled(False)
            self.btn_next_page.setEnabled(False)
            self.lbl_page_image.setPixmap(QPixmap())
            self.lbl_page_image.setText("Chưa có trang scan nào để xem trước.\nNhấn 'GỬI YÊU CẦU XỬ LÝ' để bắt đầu số hóa.")
            return

        total = len(self.preview_page_list)
        idx = max(0, min(self.current_preview_page_idx, total - 1))
        self.current_preview_page_idx = idx
        p_num = self.preview_page_list[idx]

        self.lbl_page_counter.setText(f"Trang {p_num} ({idx + 1}/{total})")
        self.btn_prev_page.setEnabled(idx > 0)
        self.btn_next_page.setEnabled(idx < total - 1)

        # Cập nhật ảnh cột trái (Scan gốc)
        page_data = self.processed_pages_data.get(p_num, {})
        img_path = page_data.get("image_path", "")
        if img_path and os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                viewport_w = self.scroll_page_preview.viewport().width() - 16
                avail_w = max(240, viewport_w)
                scaled_pixmap = pixmap.scaledToWidth(avail_w, Qt.TransformationMode.SmoothTransformation)
                self.lbl_page_image.setPixmap(scaled_pixmap)
                self.lbl_page_image.setText("")
            else:
                self.lbl_page_image.setPixmap(QPixmap())
                self.lbl_page_image.setText(f"[Lỗi đọc ảnh trang {p_num}]")
        else:
            self.lbl_page_image.setPixmap(QPixmap())
            self.lbl_page_image.setText(f"[Đang chuẩn bị ảnh trang {p_num}...]")

        # Cập nhật văn bản cột phải (Văn bản & Công thức bóc tách)
        if self.btn_view_mode_page.isChecked():
            page_text = page_data.get("markdown", "")
            self.txt_result.setPlainText(page_text)
        else:
            full_parts = []
            for pn in self.preview_page_list:
                md = self.processed_pages_data.get(pn, {}).get("markdown", "")
                full_parts.append(f"--- [Trang {pn}] ---\n" + md)
            self.txt_result.setPlainText("\n\n".join(full_parts))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'lbl_page_image') and hasattr(self, 'scroll_page_preview'):
            if self.preview_page_list and not self.lbl_page_image.pixmap().isNull():
                self._update_preview_display()

    def _on_page_completed(self, p_num: int, text: str, figs: list):
        doc_dir = self.cache_manager.get_document_cache_dir(self.last_file_path) if self.last_file_path else "cache"
        page_img_path = os.path.join(doc_dir, f"page_{p_num:04d}.png")
        self.processed_pages_data[p_num] = {
            "image_path": page_img_path,
            "markdown": text,
            "figures": figs
        }
        if p_num not in self.preview_page_list:
            self.preview_page_list.append(p_num)
            self.preview_page_list.sort()

        self.current_preview_page_idx = self.preview_page_list.index(p_num)
        self._update_preview_display()

    def _on_finished(self, docx_path: str, full_text: str, all_figures: list, all_markdown: list, per_page_image_maps: dict):
        self.btn_send.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Hoàn tất xử lý 100%!")
        self.last_docx_path = docx_path
        self.current_figures = all_figures
        self.last_markdown_pages = all_markdown
        self._update_preview_display()

        if docx_path and os.path.exists(docx_path):
            self.btn_open_word.setEnabled(True)

        base_name = os.path.splitext(os.path.basename(self.last_file_path))[0] if self.last_file_path else ""
        candidate_tex = os.path.join(os.path.abspath("output"), f"{base_name}_Converted.tex")
        if os.path.exists(candidate_tex):
            self.last_tex_path = candidate_tex
            self.btn_open_tex.setEnabled(True)

        self.btn_review_images.setEnabled(True)
        self.btn_review_images.setText(f"🖼 Xem lại & chỉnh hình ảnh ({len(self.current_figures)} hình)")

        # Auto Toggle TeX or Open Word if checked
        if docx_path and self.chk_toggle_tex.isChecked():
            WordBuilder.trigger_word_toggle_tex(docx_path)

        # Notify user
        tex_info = f"\n- File LaTeX (.tex): {os.path.basename(self.last_tex_path)}" if (self.last_tex_path and os.path.exists(self.last_tex_path)) else ""
        msg = f"Đã chuyển đổi xong tài liệu!\n- File Word: {os.path.basename(docx_path) if docx_path else 'Không tạo'}{tex_info}\n- Số hình nhận diện: {len(self.current_figures)} hình."
        if self.current_figures:
            reply = QMessageBox.question(
                self,
                "Hoàn tất chuyển đổi",
                f"{msg}\n\nBạn có muốn mở cửa sổ 'Xem lại & chỉnh khung hình ảnh' ngay không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._show_review_dialog()
        else:
            QMessageBox.information(self, "Hoàn tất chuyển đổi", msg)

    def _on_error(self, err_msg: str):
        self.btn_send.setEnabled(True)
        QMessageBox.critical(self, "Lỗi xử lý", f"Đã xảy ra lỗi: {err_msg}")

    def _open_word_file(self):
        if self.last_docx_path and os.path.exists(self.last_docx_path):
            os.startfile(self.last_docx_path)

    def _open_tex_file(self):
        if self.last_tex_path and os.path.exists(self.last_tex_path):
            os.startfile(self.last_tex_path)
        else:
            base_name = os.path.splitext(os.path.basename(self.last_file_path))[0] if self.last_file_path else ""
            candidate = os.path.join(os.path.abspath("output"), f"{base_name}_Converted.tex")
            if os.path.exists(candidate):
                self.last_tex_path = candidate
                os.startfile(candidate)
            else:
                QMessageBox.warning(self, "Chưa có file", "Chưa tìm thấy file .tex được xuất. Vui lòng chạy chuyển đổi trước!")

    def _open_output_folder(self):
        out_dir = os.path.abspath("output")
        os.makedirs(out_dir, exist_ok=True)
        os.startfile(out_dir)

    def _copy_tex_code(self):
        text = self.txt_result.toPlainText()
        if not text:
            QMessageBox.information(self, "Thông báo", "Chưa có nội dung văn bản nào để sao chép.")
            return
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        QMessageBox.information(
            self,
            "Đã sao chép mã TeX!",
            "Đã sao chép toàn bộ văn bản và mã công thức LaTeX vào Clipboard!\n\n"
            "👉 Cách dùng trong Word:\n"
            "1. Dán (Ctrl + V) vào tài liệu Word.\n"
            "2. Nhấn Ctrl + A để chọn toàn bộ văn bản.\n"
            "3. Nhấn tổ hợp phím Alt + \\ (Toggle TeX của MathType) để biến toàn bộ mã thành công thức MathType chuẩn!"
        )

    def _show_review_dialog(self):
        file_path = self.txt_file_path.text().strip() or self.last_file_path
        if not file_path or not os.path.exists(file_path):
            QMessageBox.information(self, "Thông báo", "Vui lòng chọn hoặc chuyển đổi một file tài liệu trước.")
            return

        doc_dir = self.cache_manager.get_document_cache_dir(file_path)
        fallback_img_path = os.path.join(doc_dir, "page_0001.png")

        pages = self.last_pages_processed
        if not pages and file_path.lower().endswith(".pdf"):
            try:
                pages = list(range(1, PDFProcessor.get_page_count(file_path) + 1))
            except Exception:
                pages = [1]
        elif not pages:
            pages = [1]

        dlg = ReviewDialog(
            figures_list=self.current_figures,
            page_image_path=fallback_img_path,
            parent=self,
            doc_dir=doc_dir,
            available_pages=pages,
            file_path=file_path,
            cache_manager=self.cache_manager,
            api_keys=self.config.get("api_keys", []),
            model=self.config.get("model", "gemini-2.5-flash")
        )
        if dlg.exec() == ReviewDialog.DialogCode.Accepted:
            # User accepted review/adjustments, re-generate Word with selected/updated figures
            self.btn_review_images.setText(f"🖼 Xem lại & chỉnh hình ảnh ({len(self.current_figures)} hình)")
            self._rebuild_word_with_figures()

    def _rebuild_word_with_figures(self):
        """Re-synthesizes the Word document using the updated figures and crop selections without re-calling Gemini."""
        if not self.last_file_path or not self.last_markdown_pages:
            return

        base_name = os.path.splitext(os.path.basename(self.last_file_path))[0]
        out_dir = os.path.abspath("output")
        docx_path = os.path.join(out_dir, f"{base_name}_Converted.docx")

        # Build per-page image maps containing ONLY selected figures
        selected_maps = {}
        for fig in self.current_figures:
            p_num = fig.get("page_num", 1)
            if p_num not in selected_maps:
                selected_maps[p_num] = {}
            if fig.get("selected", True):
                selected_maps[p_num][fig["id"]] = fig["cropped_path"]

        is_tex_mode = self.chk_toggle_tex.isChecked() if hasattr(self, 'chk_toggle_tex') else False
        wb = WordBuilder(
            font_name="Times New Roman",
            font_size_pt=13.0,
            convert_to_omml=not is_tex_mode,
            toggle_tex_mode=is_tex_mode,
            format_multiple_choice=self.chk_format_mc.isChecked() if hasattr(self, 'chk_format_mc') else True,
            smart_layout=self.chk_smart_layout.isChecked() if hasattr(self, 'chk_smart_layout') else True
        )
        first_page = self.last_markdown_pages[0].strip() if self.last_markdown_pages else ""
        if not (first_page.startswith("|") or first_page.startswith("#")):
            wb.add_header_title(f"TÀI LIỆU TOÁN HỌC: {base_name.upper()}")

        pages_to_build = self.last_pages_processed or list(range(1, len(self.last_markdown_pages) + 1))
        for idx, p_num in enumerate(pages_to_build):
            p_text = self.last_markdown_pages[idx] if idx < len(self.last_markdown_pages) else ""
            p_imgs = selected_maps.get(p_num, {})
            wb.add_page_content(p_num, p_text, p_imgs)
            if idx < len(pages_to_build) - 1:
                wb.doc.add_page_break()

        try:
            wb.save(docx_path)
        except PermissionError:
            docx_path = os.path.join(out_dir, f"{base_name}_Converted_{time.strftime('%H%M%S')}.docx")
            wb.save(docx_path)

        self.last_docx_path = docx_path
        self.btn_open_word.setEnabled(True)

        # Cập nhật song song file LaTeX (.tex) nếu tùy chọn xuất LaTeX đang bật
        if hasattr(self, 'chk_export_tex') and self.chk_export_tex.isChecked():
            from core.latex_exporter import LatexExporter
            tex_path = LatexExporter.export_to_tex(
                base_name=base_name,
                all_markdown_pages=self.last_markdown_pages,
                per_page_image_maps=selected_maps,
                output_dir=out_dir
            )
            self.last_tex_path = tex_path
            self.btn_open_tex.setEnabled(True)

        QMessageBox.information(
            self,
            "Cập nhật thành công",
            f"Đã cập nhật file Word & LaTeX với các hình ảnh và khung cắt mới:\n{os.path.basename(docx_path)}"
        )
