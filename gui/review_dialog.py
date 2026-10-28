import os
from typing import List, Dict, Any, Tuple, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea,
    QWidget, QCheckBox, QFileDialog, QMessageBox, QFrame, QInputDialog
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from PIL import Image

from core.image_cropper import ImageCropper
from gui.crop_editor_dialog import CropEditorDialog

class FigureCard(QFrame):
    def __init__(self, fig_data: Dict[str, Any], page_image_path: str, parent_dialog):
        super().__init__()
        self.fig_data = fig_data
        self.page_image_path = fig_data.get("page_image_path") or page_image_path
        self.parent_dialog = parent_dialog

        is_blank = fig_data.get("is_blank", False)
        reject_reason = fig_data.get("reject_reason", "")
        border_color = "#f59e0b" if is_blank else "#d0d7de"
        bg_color = "#fffbeb" if is_blank else "#ffffff"

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            FigureCard {{
                border: 1px solid {border_color};
                border-radius: 6px;
                background-color: {bg_color};
                margin-bottom: 8px;
            }}
        """)

        layout = QVBoxLayout(self)

        # Header bar
        header_layout = QHBoxLayout()
        fig_num = fig_data.get("display_num", 1)
        p_num = fig_data.get("page_num", "")
        page_label = f" (Trang {p_num})" if p_num else ""
        is_manual = " [Thêm thủ công]" if fig_data.get("is_manual") else ""
        blank_tag = f" ⚠️ [Đã lọc: {reject_reason}]" if is_blank else ""

        self.checkbox = QCheckBox(f"Hình {fig_num}{page_label}{is_manual}{blank_tag} — chèn vào Word")
        self.checkbox.setChecked(fig_data.get("selected", not is_blank))
        if is_blank:
            self.checkbox.setStyleSheet("font-weight: bold; font-size: 13px; color: #b45309;")
            self.checkbox.setToolTip(f"Hình bị nhận diện là ảnh rác/rỗng ({reject_reason}). Đã tự động bỏ chọn để tránh chèn vào Word. Bạn có thể tích chọn lại hoặc bấm 'Chỉnh khung'.")
        else:
            self.checkbox.setStyleSheet("font-weight: bold; font-size: 13px; color: #003366;")
        header_layout.addWidget(self.checkbox)

        header_layout.addStretch()

        btn_rot_cw = QPushButton("⟳ Xoay phải")
        btn_rot_cw.setToolTip("Xoay hình 90° theo chiều kim đồng hồ (nếu hình bị nằm dọc/ngang)")
        btn_rot_cw.setStyleSheet("""
            QPushButton {
                background-color: #e0f2fe;
                border: 1px solid #bae6fd;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
                color: #0369a1;
            }
            QPushButton:hover {
                background-color: #bae6fd;
            }
        """)
        btn_rot_cw.clicked.connect(lambda: self._rotate_figure(90))
        header_layout.addWidget(btn_rot_cw)

        btn_rot_ccw = QPushButton("⟲ Xoay trái")
        btn_rot_ccw.setToolTip("Xoay hình 90° ngược chiều kim đồng hồ")
        btn_rot_ccw.setStyleSheet("""
            QPushButton {
                background-color: #e0f2fe;
                border: 1px solid #bae6fd;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
                color: #0369a1;
            }
            QPushButton:hover {
                background-color: #bae6fd;
            }
        """)
        btn_rot_ccw.clicked.connect(lambda: self._rotate_figure(-90))
        header_layout.addWidget(btn_rot_ccw)

        btn_edit = QPushButton("✏ Chỉnh khung")
        btn_edit.setStyleSheet("""
            QPushButton {
                background-color: #fff3cd;
                border: 1px solid #ffeeba;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
                color: #856404;
            }
            QPushButton:hover {
                background-color: #ffe8a1;
            }
        """)
        btn_edit.clicked.connect(self._open_crop_editor)
        header_layout.addWidget(btn_edit)

        btn_del = QPushButton("🗑 Xóa")
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
                color: #721c24;
            }
            QPushButton:hover {
                background-color: #f1b0b7;
            }
        """)
        btn_del.clicked.connect(lambda: self.parent_dialog.remove_figure(self))
        header_layout.addWidget(btn_del)

        # Button: Toggle between AI Redraw and Original Crop if both exist
        self.btn_toggle_version = QPushButton("🔄 Đổi sang ảnh gốc" if fig_data.get("redraw_path") else "✨ Dùng hình AI")
        self.btn_toggle_version.setToolTip("Chuyển đổi qua lại giữa ảnh crop gốc và hình vector do AI vẽ lại")
        self.btn_toggle_version.setVisible(bool(fig_data.get("original_path") and fig_data.get("redraw_path")))
        self.btn_toggle_version.setStyleSheet("""
            QPushButton {
                background-color: #f0fdf4;
                border: 1px solid #bbf7d0;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
                color: #15803d;
            }
            QPushButton:hover {
                background-color: #dcfce7;
            }
        """)
        self.btn_toggle_version.clicked.connect(self._toggle_version)
        header_layout.addWidget(self.btn_toggle_version)

        # Button: AI Redraw
        self.btn_ai_redraw = QPushButton("✨ AI vẽ lại hình")
        self.btn_ai_redraw.setToolTip("Dùng AI phân tích đề bài và tự động vẽ lại hình học phẳng 2D, thẳng góc trực diện, siêu nét 300 DPI")
        self.btn_ai_redraw.setStyleSheet("""
            QPushButton {
                background-color: #f3e8ff;
                border: 1px solid #d8b4fe;
                padding: 4px 10px;
                border-radius: 4px;
                font-weight: bold;
                color: #6b21a8;
            }
            QPushButton:hover {
                background-color: #e9d5ff;
            }
        """)
        self.btn_ai_redraw.clicked.connect(self._ai_redraw_figure)
        header_layout.addWidget(self.btn_ai_redraw)

        layout.addLayout(header_layout)

        # Thumbnail Image
        self.lbl_img = QLabel()
        self.lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_img.setStyleSheet("background-color: #fafafa; border: 1px dashed #e1e4e8; padding: 6px;")
        self._update_thumbnail()
        layout.addWidget(self.lbl_img)

    def _rotate_figure(self, angle: int):
        crop_path = self.fig_data["cropped_path"]
        if ImageCropper.rotate_cropped_file(crop_path, angle):
            self._update_thumbnail()

    def _toggle_version(self):
        orig = self.fig_data.get("original_path")
        rd = self.fig_data.get("redraw_path")
        if not orig or not rd:
            return

        cur = self.fig_data["cropped_path"]
        if cur == rd:
            self.fig_data["cropped_path"] = orig
            self.btn_toggle_version.setText("✨ Đổi sang hình AI")
        else:
            self.fig_data["cropped_path"] = rd
            self.btn_toggle_version.setText("🔄 Đổi sang ảnh gốc")
        self._update_thumbnail()

    def _ai_redraw_figure(self):
        crop_path = self.fig_data.get("original_path") or self.fig_data["cropped_path"]
        if not os.path.exists(crop_path):
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy file ảnh gốc để vẽ lại.")
            return

        api_keys = getattr(self.parent_dialog, "api_keys", []) or []
        model = getattr(self.parent_dialog, "model", "gemini-2.5-flash")

        if not api_keys:
            QMessageBox.warning(
                self,
                "Chưa có API Key",
                "Vui lòng cấu hình Gemini API Key trong tab Cấu hình để sử dụng tính năng AI vẽ lại hình học!"
            )
            return

        self.btn_ai_redraw.setText("⏳ Đang vẽ...")
        self.btn_ai_redraw.setEnabled(False)
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            from core.ai_figure_artist import AIGeometryArtist
            out_redraw_path = f"{os.path.splitext(crop_path)[0]}_ai_redraw.png"
            desc = self.fig_data.get("description", "")
            ctx = self.fig_data.get("context_text", "")

            new_path = AIGeometryArtist.redraw_figure(
                image_path=crop_path,
                output_path=out_redraw_path,
                api_keys=api_keys,
                model=model,
                description=desc,
                context_text=ctx,
                timeout_seconds=30
            )

            if new_path and os.path.exists(new_path):
                if "original_path" not in self.fig_data:
                    self.fig_data["original_path"] = self.fig_data["cropped_path"]
                self.fig_data["redraw_path"] = new_path
                self.fig_data["cropped_path"] = new_path
                self.fig_data["is_blank"] = False
                self.fig_data["selected"] = True
                self.checkbox.setChecked(True)
                self._update_thumbnail()
                self.btn_toggle_version.setVisible(True)
                self.btn_toggle_version.setText("🔄 Đổi sang ảnh gốc")
                self.btn_ai_redraw.setText("✨ Đã vẽ lại")
                QMessageBox.information(
                    self,
                    "Thành công",
                    "Đã dùng AI tái tạo lại hình học thẳng góc, chuẩn xác và siêu nét 300 DPI!"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Không thể vẽ lại",
                    "AI không thể vẽ lại hình này (hoặc hình không thuộc dạng hình học). Đã giữ nguyên ảnh gốc."
                )
                self.btn_ai_redraw.setText("✨ AI vẽ lại hình")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Có lỗi xảy ra khi vẽ lại: {str(e)}")
            self.btn_ai_redraw.setText("✨ AI vẽ lại hình")
        finally:
            self.btn_ai_redraw.setEnabled(True)

    def _update_thumbnail(self):
        crop_path = self.fig_data["cropped_path"]
        if os.path.exists(crop_path):
            pix = QPixmap(crop_path)
            # Scale down proportionally so it fits nicely inside card without overflowing width or height
            max_w = 720
            max_h = 240
            if pix.width() > max_w or pix.height() > max_h:
                pix = pix.scaled(max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_img.setPixmap(pix)

    def _open_crop_editor(self):
        try:
            page_img_path = self.fig_data.get("page_image_path") or self.page_image_path
            if not page_img_path or not os.path.exists(page_img_path):
                QMessageBox.warning(self, "Lỗi", f"Không tìm thấy file ảnh gốc của trang tại:\n{page_img_path}")
                return

            with Image.open(page_img_path) as page_img:
                w, h = page_img.size

                # Extract box_2d (normalized 0..1000)
                box_2d = self.fig_data.get("box_2d", [0, 0, 1000, 1000])
                ymin, xmin, ymax, xmax = box_2d
                scale_x = w / 1000.0 if max(box_2d) > 1.0 else w
                scale_y = h / 1000.0 if max(box_2d) > 1.0 else h

                cur_l = max(0, min(w - 1, int(xmin * scale_x)))
                cur_t = max(0, min(h - 1, int(ymin * scale_y)))
                cur_r = max(cur_l + 10, min(w, int(xmax * scale_x)))
                cur_b = max(cur_t + 10, min(h, int(ymax * scale_y)))

                dlg = CropEditorDialog(page_img_path, (cur_l, cur_t, cur_r, cur_b), self)
                dlg.setWindowTitle(f"✏ Chỉnh khung Hình {self.fig_data.get('display_num', '')} (Trang {self.fig_data.get('page_num', '')})")
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    new_l, new_t, new_r, new_b = dlg.result_pixel_box
                    # Re-crop image
                    crop_path = self.fig_data["cropped_path"]
                    ImageCropper.crop_pixel_box(page_img, (new_l, new_t, new_r, new_b), crop_path)
                    if getattr(dlg, "result_rotation", 0) != 0:
                        ImageCropper.rotate_cropped_file(crop_path, dlg.result_rotation)

                    # Update normalized coordinates
                    self.fig_data["box_2d"] = [
                        (new_t / h) * 1000.0,
                        (new_l / w) * 1000.0,
                        (new_b / h) * 1000.0,
                        (new_r / w) * 1000.0
                    ]
                    self.fig_data["is_blank"] = False
                    self.fig_data["selected"] = True

                    p_num = self.fig_data.get("page_num", "")
                    page_label = f" (Trang {p_num})" if p_num else ""
                    is_manual = " [Thêm thủ công]" if self.fig_data.get("is_manual") else ""
                    self.checkbox.setText(f"Hình {self.fig_data.get('display_num', 1)}{page_label}{is_manual} — chèn vào Word")
                    self.checkbox.setChecked(True)
                    self.checkbox.setStyleSheet("font-weight: bold; font-size: 13px; color: #003366;")
                    self.checkbox.setToolTip("")
                    self.setStyleSheet("""
                        FigureCard {
                            border: 1px solid #d0d7de;
                            border-radius: 6px;
                            background-color: #ffffff;
                            margin-bottom: 8px;
                        }
                    """)

                    self._update_thumbnail()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi chỉnh khung", f"Không thể mở bộ chỉnh khung: {str(e)}")

    def is_selected(self) -> bool:
        return self.checkbox.isChecked()

    def set_selected(self, val: bool):
        self.checkbox.setChecked(val)


class ReviewDialog(QDialog):
    def __init__(
        self,
        figures_list: List[Dict[str, Any]],
        page_image_path: str,
        parent=None,
        doc_dir: Optional[str] = None,
        available_pages: Optional[List[int]] = None,
        file_path: Optional[str] = None,
        cache_manager: Optional[Any] = None,
        api_keys: Optional[List[str]] = None,
        model: str = "gemini-2.5-flash"
    ):
        super().__init__(parent)
        self.api_keys = api_keys or []
        self.model = model
        self.setWindowTitle(f"Xem lại & Quản lý hình ảnh ({len(figures_list)} hình)")
        self.resize(960, 750)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.figures_list = figures_list
        self.page_image_path = page_image_path
        self.doc_dir = doc_dir or (os.path.dirname(page_image_path) if page_image_path else "")
        self.available_pages = available_pages or []
        self.file_path = file_path
        self.cache_manager = cache_manager
        self.cards: List[FigureCard] = []

        layout = QVBoxLayout(self)

        # Header note & Top Buttons
        header_h = QHBoxLayout()
        lbl_note = QLabel(
            "<b>Mẹo:</b> Tick chọn hình cần chèn vào Word. Bấm <b>\"Chỉnh khung\"</b> để căn lại vị trí. "
            "Nếu AI bỏ sót hình nào, bấm <b>\"➕ Thêm hình mới\"</b> để cắt bổ sung!"
        )
        lbl_note.setStyleSheet("background-color: #fff9e6; color: #333333; padding: 10px; border-radius: 5px;")
        lbl_note.setWordWrap(True)
        header_h.addWidget(lbl_note, 1)

        btn_add_top = QPushButton("➕ Thêm hình mới")
        btn_add_top.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        btn_add_top.clicked.connect(self._add_manual_figure)
        header_h.addWidget(btn_add_top)

        self.btn_maximize = QPushButton("🗖 Phóng to")
        self.btn_maximize.setToolTip("Phóng to toàn màn hình / Thu nhỏ cửa sổ")
        self.btn_maximize.setStyleSheet("""
            QPushButton {
                background-color: #f3f4f6;
                color: #1f2937;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 14px;
                border: 1px solid #d1d5db;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e5e7eb;
            }
        """)
        self.btn_maximize.clicked.connect(self._toggle_maximize)
        header_h.addWidget(self.btn_maximize)

        layout.addLayout(header_h)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)

        self._render_cards()

        scroll.setWidget(self.container)
        layout.addWidget(scroll)

        # Bottom actions
        bottom_layout = QHBoxLayout()

        btn_select_all = QPushButton("Chọn tất cả")
        btn_select_all.clicked.connect(self._select_all)
        bottom_layout.addWidget(btn_select_all)

        btn_unselect_all = QPushButton("Bỏ tất cả")
        btn_unselect_all.clicked.connect(self._unselect_all)
        bottom_layout.addWidget(btn_unselect_all)

        btn_add_bottom = QPushButton("➕ Cắt thêm hình")
        btn_add_bottom.setStyleSheet("font-weight: bold; color: #0078d4;")
        btn_add_bottom.clicked.connect(self._add_manual_figure)
        bottom_layout.addWidget(btn_add_bottom)

        btn_export_imgs = QPushButton("Xuất ảnh ▼")
        btn_export_imgs.clicked.connect(self._export_images)
        bottom_layout.addWidget(btn_export_imgs)

        bottom_layout.addStretch()

        btn_ok = QPushButton("✔ Đồng ý & Chèn vào Word")
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 24px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        btn_ok.clicked.connect(self._accept_and_save)
        bottom_layout.addWidget(btn_ok)

        layout.addLayout(bottom_layout)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.btn_maximize.setText("🗖 Phóng to")
        else:
            self.showMaximized()
            self.btn_maximize.setText("🗗 Thu nhỏ")

    def changeEvent(self, event):
        if event.type() == event.Type.WindowStateChange:
            if hasattr(self, 'btn_maximize'):
                if self.isMaximized():
                    self.btn_maximize.setText("🗗 Thu nhỏ")
                else:
                    self.btn_maximize.setText("🗖 Phóng to")
        super().changeEvent(event)

    def _render_cards(self):
        # Clear existing widgets
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.cards.clear()
        if not self.figures_list:
            lbl_empty = QLabel("\nChưa có hình ảnh nào được nhận diện hoặc tạo.\nHãy bấm nút <b>'➕ Thêm hình mới'</b> ở trên để cắt thêm hình từ trang sách!\n")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_empty.setStyleSheet("color: #666666; font-size: 14px;")
            self.container_layout.addWidget(lbl_empty)
        else:
            for fig in self.figures_list:
                card = FigureCard(fig, self.page_image_path, self)
                self.cards.append(card)
                self.container_layout.addWidget(card)

        self.container_layout.addStretch()

    def remove_figure(self, card: FigureCard):
        res = QMessageBox.question(
            self,
            "Xác nhận xóa hình",
            f"Bạn có chắc muốn xóa Hình {card.fig_data.get('display_num', '')} (Trang {card.fig_data.get('page_num', '')}) khỏi danh sách?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            if card in self.cards:
                self.cards.remove(card)
            if card.fig_data in self.figures_list:
                self.figures_list.remove(card.fig_data)
            card.deleteLater()
            self.setWindowTitle(f"Xem lại & Quản lý hình ảnh ({len(self.figures_list)} hình)")

    def _add_manual_figure(self):
        try:
            # 1. Determine which page to add figure from
            pages = self.available_pages or []
            if not pages:
                seen_pages = sorted(list(set(f.get("page_num", 1) for f in self.figures_list)))
                pages = seen_pages if seen_pages else [1]

            selected_page = pages[0]
            if len(pages) > 1:
                items = [f"Trang {p}" for p in pages]
                choice, ok = QInputDialog.getItem(
                    self, "Chọn trang cắt hình", "Chọn trang sách cần cắt thêm hình vẽ:", items, 0, False
                )
                if not ok or not choice:
                    return
                selected_page = int(choice.replace("Trang", "").strip())

            # 2. Locate or render page image
            doc_dir = self.doc_dir or (os.path.dirname(self.page_image_path) if self.page_image_path else "cache")
            os.makedirs(doc_dir, exist_ok=True)
            page_img_path = os.path.join(doc_dir, f"page_{selected_page:04d}.png")

            if not os.path.exists(page_img_path):
                if self.file_path and os.path.exists(self.file_path):
                    if self.file_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                        page_img_path = self.file_path
                    else:
                        from core.pdf_processor import PDFProcessor
                        PDFProcessor.render_page_to_image(self.file_path, selected_page, dpi=250, save_path=page_img_path, enhance=True)
                elif self.page_image_path and os.path.exists(self.page_image_path):
                    page_img_path = self.page_image_path
                else:
                    QMessageBox.warning(self, "Lỗi", f"Không tìm thấy ảnh của trang {selected_page} để cắt hình.")
                    return

            with Image.open(page_img_path) as page_img:
                w, h = page_img.size

                # Default initial crop box centered on page
                box_w = min(400, int(w * 0.6))
                box_h = min(300, int(h * 0.4))
                init_l = max(0, (w - box_w) // 2)
                init_t = max(0, (h - box_h) // 2)
                initial_pixel_box = (init_l, init_t, init_l + box_w, init_t + box_h)

                dlg = CropEditorDialog(page_img_path, initial_pixel_box, self)
                dlg.setWindowTitle(f"➕ Kéo thả khung cắt hình mới - Trang {selected_page}")
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    new_l, new_t, new_r, new_b = dlg.result_pixel_box
                    
                    # Create unique figure ID and sequential display number
                    existing_nums = [f.get("display_num", 0) for f in self.figures_list]
                    new_disp_num = (max(existing_nums) + 1) if existing_nums else 1
                    manual_count = sum(1 for f in self.figures_list if "MANUAL" in str(f.get("id", ""))) + 1
                    fig_id = f"HINH_MANUAL_{manual_count}"
                    
                    crop_filename = f"page_{selected_page:04d}_{fig_id}.png"
                    crop_path = os.path.join(doc_dir, crop_filename)

                    ImageCropper.crop_pixel_box(page_img, (new_l, new_t, new_r, new_b), crop_path)

                    box_2d = [
                        (new_t / h) * 1000.0,
                        (new_l / w) * 1000.0,
                        (new_b / h) * 1000.0,
                        (new_r / w) * 1000.0
                    ]

                    new_fig = {
                        "id": fig_id,
                        "page_num": selected_page,
                        "page_image_path": page_img_path,
                        "box_2d": box_2d,
                        "cropped_path": crop_path,
                        "display_num": new_disp_num,
                        "selected": True,
                        "is_manual": True
                    }

                    self.figures_list.append(new_fig)
                
                # Re-render cards list
                self._render_cards()
                
                # Save to cache if cache_manager is present
                if self.cache_manager and doc_dir:
                    cached = self.cache_manager.get_page_result(doc_dir, selected_page)
                    if cached:
                        figs = cached.get("figures", [])
                        figs.append(new_fig)
                        cached["figures"] = figs
                        self.cache_manager.save_page_result(doc_dir, selected_page, cached)

                self.setWindowTitle(f"Xem lại & Quản lý hình ảnh ({len(self.figures_list)} hình)")
                QMessageBox.information(
                    self,
                    "Thành công",
                    f"Đã thêm thành công <b>Hình {new_disp_num}</b> (Trang {selected_page})!<br>"
                    f"Hình đã được lưu và sẽ được tự động chèn vào file Word khi bạn bấm <b>'Đồng ý'</b>."
                )

        except Exception as e:
            QMessageBox.critical(self, "Lỗi thêm hình", f"Không thể thêm hình mới: {str(e)}")

    def _select_all(self):
        for c in self.cards:
            c.set_selected(True)

    def _unselect_all(self):
        for c in self.cards:
            c.set_selected(False)

    def _export_images(self):
        out_dir = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất ảnh")
        if out_dir:
            import shutil
            count = 0
            for card in self.cards:
                if card.is_selected():
                    src = card.fig_data["cropped_path"]
                    if os.path.exists(src):
                        dst = os.path.join(out_dir, os.path.basename(src))
                        shutil.copy2(src, dst)
                        count += 1
            QMessageBox.information(self, "Thành công", f"Đã xuất {count} hình ảnh vào: {out_dir}")

    def _accept_and_save(self):
        for card in self.cards:
            card.fig_data["selected"] = card.is_selected()
        self.accept()

    def get_selected_figure_ids(self) -> List[str]:
        return [c.fig_data["id"] for c in self.cards if c.is_selected()]
