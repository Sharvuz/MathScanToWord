import os
from typing import Tuple, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QMessageBox, QFrame
)
from PyQt6.QtGui import QPixmap, QPen, QBrush, QColor, QPainter
from PyQt6.QtCore import Qt, QRectF, QPointF
from PIL import Image

class ResizableRectItem(QGraphicsRectItem):
    HANDLE_SIZE = 10.0
    HANDLE_HIT_PAD = 5.0
    MIN_SIZE = 20.0

    def __init__(self, rect: QRectF, max_w: float, max_h: float, dialog=None):
        super().__init__(rect)
        self.max_w = max_w
        self.max_h = max_h
        self.dialog = dialog

        self.active_handle: Optional[str] = None
        self.hovered_handle: Optional[str] = None
        self.drag_start_scene_pos: Optional[QPointF] = None
        self.initial_item_pos: Optional[QPointF] = None
        self.initial_rect: Optional[QRectF] = None

        self.setPen(QPen(QColor(0, 160, 45), 2.5, Qt.PenStyle.SolidLine))
        self.setBrush(QBrush(QColor(0, 200, 50, 40)))

        self.setAcceptHoverEvents(True)
        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

    def get_handles(self) -> dict:
        rect = self.rect()
        w = rect.width()
        h = rect.height()
        h_sz = self.HANDLE_SIZE
        half = h_sz / 2.0

        return {
            "TL": QRectF(-half, -half, h_sz, h_sz),
            "T":  QRectF(w / 2.0 - half, -half, h_sz, h_sz),
            "TR": QRectF(w - half, -half, h_sz, h_sz),
            "R":  QRectF(w - half, h / 2.0 - half, h_sz, h_sz),
            "BR": QRectF(w - half, h - half, h_sz, h_sz),
            "B":  QRectF(w / 2.0 - half, h - half, h_sz, h_sz),
            "BL": QRectF(-half, h - half, h_sz, h_sz),
            "L":  QRectF(-half, h / 2.0 - half, h_sz, h_sz),
        }

    def get_handle_at(self, pt: QPointF) -> Optional[str]:
        handles = self.get_handles()
        pad = self.HANDLE_HIT_PAD

        # 1. Check corner handles first (highest priority)
        for h_name in ("TL", "TR", "BR", "BL"):
            if handles[h_name].adjusted(-pad, -pad, pad, pad).contains(pt):
                return h_name

        # 2. Check edge handles
        for h_name in ("T", "B", "L", "R"):
            if handles[h_name].adjusted(-pad, -pad, pad, pad).contains(pt):
                return h_name

        # 3. Check inside rectangle or close to borders
        if self.rect().adjusted(-3, -3, 3, 3).contains(pt):
            return "MOVE"

        return None

    def boundingRect(self) -> QRectF:
        pad = self.HANDLE_SIZE + self.HANDLE_HIT_PAD
        return self.rect().adjusted(-pad, -pad, pad, pad)

    def shape(self):
        from PyQt6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRect(self.rect().adjusted(-3, -3, 3, 3))
        pad = self.HANDLE_HIT_PAD
        for h_rect in self.get_handles().values():
            path.addRect(h_rect.adjusted(-pad, -pad, pad, pad))
        return path

    def _update_cursor(self, handle: Optional[str]):
        if handle in ("TL", "BR"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif handle in ("TR", "BL"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif handle in ("T", "B"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif handle in ("L", "R"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif handle == "MOVE":
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def hoverEnterEvent(self, event):
        self.hovered_handle = self.get_handle_at(event.pos())
        self._update_cursor(self.hovered_handle)
        self.update()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        new_h = self.get_handle_at(event.pos())
        if new_h != self.hovered_handle:
            self.hovered_handle = new_h
            self._update_cursor(new_h)
            self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.hovered_handle = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.get_handle_at(event.pos())
            if handle:
                self.active_handle = handle
                self.drag_start_scene_pos = event.scenePos()
                self.initial_item_pos = self.pos()
                self.initial_rect = self.rect()
                self._update_cursor(handle)
                self.update()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.active_handle and self.drag_start_scene_pos and self.initial_item_pos and self.initial_rect:
            current_scene_pos = event.scenePos()
            dx = current_scene_pos.x() - self.drag_start_scene_pos.x()
            dy = current_scene_pos.y() - self.drag_start_scene_pos.y()

            init_l = self.initial_item_pos.x()
            init_t = self.initial_item_pos.y()
            init_w = self.initial_rect.width()
            init_h = self.initial_rect.height()
            init_r = init_l + init_w
            init_b = init_t + init_h

            new_l = init_l
            new_t = init_t
            new_r = init_r
            new_b = init_b

            if self.active_handle == "MOVE":
                new_l = init_l + dx
                new_t = init_t + dy
                new_r = init_r + dx
                new_b = init_b + dy

                # Clamp move within [0, 0, max_w, max_h]
                if new_l < 0:
                    new_l = 0.0
                    new_r = init_w
                elif new_r > self.max_w:
                    new_r = float(self.max_w)
                    new_l = max(0.0, float(self.max_w) - init_w)

                if new_t < 0:
                    new_t = 0.0
                    new_b = init_h
                elif new_b > self.max_h:
                    new_b = float(self.max_h)
                    new_t = max(0.0, float(self.max_h) - init_h)
            else:
                # Resize handles
                if self.active_handle in ("R", "TR", "BR"):
                    new_r = min(float(self.max_w), max(init_l + self.MIN_SIZE, init_r + dx))
                elif self.active_handle in ("L", "TL", "BL"):
                    new_l = max(0.0, min(init_r - self.MIN_SIZE, init_l + dx))

                if self.active_handle in ("B", "BL", "BR"):
                    new_b = min(float(self.max_h), max(init_t + self.MIN_SIZE, init_b + dy))
                elif self.active_handle in ("T", "TL", "TR"):
                    new_t = max(0.0, min(init_b - self.MIN_SIZE, init_t + dy))

            self.prepareGeometryChange()
            self.setRect(0, 0, new_r - new_l, new_b - new_t)
            self.setPos(new_l, new_t)

            if self.dialog:
                self.dialog.update_info_label()

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.active_handle:
            self.active_handle = None
            self.drag_start_scene_pos = None
            self.initial_item_pos = None
            self.initial_rect = None
            self.hovered_handle = self.get_handle_at(event.pos())
            self._update_cursor(self.hovered_handle)
            self.update()
            if self.dialog:
                self.dialog.update_info_label()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange and self.scene():
            if not self.active_handle:
                new_pos = value
                rect = self.rect()
                x = max(0.0, min(self.max_w - rect.width(), new_pos.x()))
                y = max(0.0, min(self.max_h - rect.height(), new_pos.y()))
                if self.dialog:
                    self.dialog.update_info_label(override_pos=QPointF(x, y))
                return QPointF(x, y)
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.rect()

        # 1. Fill semi-transparent background
        painter.fillRect(rect, QBrush(QColor(0, 200, 60, 35)))

        # 2. Main border
        border_pen = QPen(QColor(0, 160, 45), 2.5, Qt.PenStyle.SolidLine)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # 3. Draw 8 Word-style handles
        handles = self.get_handles()
        default_handle_pen = QPen(QColor(0, 130, 35), 2)
        active_handle_pen = QPen(QColor(0, 90, 15), 2.5)

        for name, h_rect in handles.items():
            if name == self.active_handle or name == self.hovered_handle:
                painter.setPen(active_handle_pen)
                painter.setBrush(QBrush(QColor(0, 210, 60)))  # Highlight active/hovered handle
            else:
                painter.setPen(default_handle_pen)
                painter.setBrush(QBrush(QColor(255, 255, 255)))  # White fill like Word
            painter.drawRoundedRect(h_rect, 2.0, 2.0)


class CropGraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, dialog, parent=None):
        super().__init__(scene, parent)
        self.dialog = dialog
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.is_drawing = False
        self.draw_start_pos = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.scale(1.15, 1.15)
        elif delta < 0:
            self.scale(0.85, 0.85)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            item = self.scene().itemAt(scene_pos, self.transform())
            if item == self.dialog.crop_item:
                super().mousePressEvent(event)
                return

            # Clicked outside crop item: begin drag-to-draw
            self.is_drawing = True
            self.draw_start_pos = scene_pos
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_drawing and self.draw_start_pos:
            scene_pos = self.mapToScene(event.pos())
            img_w = self.dialog.img_w
            img_h = self.dialog.img_h

            x1 = max(0.0, min(float(img_w), self.draw_start_pos.x()))
            y1 = max(0.0, min(float(img_h), self.draw_start_pos.y()))
            x2 = max(0.0, min(float(img_w), scene_pos.x()))
            y2 = max(0.0, min(float(img_h), scene_pos.y()))

            left = min(x1, x2)
            top = min(y1, y2)
            w = max(20.0, abs(x2 - x1))
            h = max(20.0, abs(y2 - y1))

            self.dialog.crop_item.prepareGeometryChange()
            self.dialog.crop_item.setRect(0, 0, w, h)
            self.dialog.crop_item.setPos(left, top)
            self.dialog.update_info_label()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_drawing:
            self.is_drawing = False
            scene_pos = self.mapToScene(event.pos())
            if self.draw_start_pos:
                dist = (scene_pos - self.draw_start_pos).manhattanLength()
                if dist < 12:
                    # Single click on page: move center of crop box to clicked position
                    self.dialog.center_crop_at(self.draw_start_pos)
                else:
                    self.dialog.update_info_label()
            self.draw_start_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            self.dialog.update_info_label()


class CropEditorDialog(QDialog):
    def __init__(self, page_image_path: str, initial_pixel_box: Tuple[int, int, int, int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chỉnh khung cắt hình ảnh")
        self.resize(1000, 820)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.page_image_path = page_image_path
        self.image_path = page_image_path  # Alias to ensure backwards compatibility
        self.result_pixel_box = initial_pixel_box
        self.crop_rotation = 0
        self.result_rotation = 0

        if not os.path.exists(page_image_path):
            raise FileNotFoundError(f"Không tìm thấy file ảnh gốc: {page_image_path}")

        # Load image size
        with Image.open(page_image_path) as im:
            self.img_w, self.img_h = im.size

        layout = QVBoxLayout(self)

        instruction = QLabel(
            "<b>💡 Hướng dẫn chỉnh khung cắt:</b><br>"
            "• <b>Kéo 8 điểm nút (như trong Word):</b> Đưa chuột vào 4 góc hoặc 4 cạnh của khung viền để co dãn trực tiếp bằng chuột.<br>"
            "• <b>Di chuyển khung:</b> Nhấp giữ chuột vào giữa khung xanh để kéo thả, hoặc <b>nhấp chuột vào bất cứ đâu</b> để đưa khung tới đó.<br>"
            "• <b>Vẽ khung mới:</b> Nhấn giữ và kéo chuột ở vùng ảnh trống bên ngoài để vẽ lại khung mới.<br>"
            "• <b>Phím mũi tên:</b> Dùng ⬅ ➡ ⬆ ⬇ để dịch chuyển khung (giữ phím Shift để co dãn kích thước)."
        )
        instruction.setStyleSheet("background-color: #f0f7ff; color: #004085; padding: 10px 14px; border-radius: 6px; font-size: 13px; line-height: 1.4;")
        layout.addWidget(instruction)

        # Graphics Scene & Custom View
        self.scene = QGraphicsScene(self)
        self.view = CropGraphicsView(self.scene, self, self)
        layout.addWidget(self.view)

        # Background image
        pix = QPixmap(page_image_path)
        self.scene.addPixmap(pix)

        # Initial crop box
        l, t, r, b = initial_pixel_box
        rect_w = max(40, r - l)
        rect_h = max(40, b - t)
        self.crop_item = ResizableRectItem(QRectF(0, 0, rect_w, rect_h), self.img_w, self.img_h, self)
        self.crop_item.setPos(l, t)
        self.scene.addItem(self.crop_item)

        # Center view
        self.view.centerOn(self.crop_item)

        # Live Info Label Bar
        info_bar = QHBoxLayout()
        self.lbl_info = QLabel()
        self.lbl_info.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 13px; padding: 4px;")
        info_bar.addWidget(self.lbl_info)
        info_bar.addStretch()
        layout.addLayout(info_bar)

        # Row 1 of controls: Presets & Zoom
        r1_layout = QHBoxLayout()
        r1_layout.addWidget(QLabel("<b>Cỡ mẫu nhanh:</b>"))
        
        btn_pre_sm = QPushButton("Nhỏ (300×200)")
        btn_pre_sm.clicked.connect(lambda: self._apply_preset(300, 200))
        r1_layout.addWidget(btn_pre_sm)

        btn_pre_md = QPushButton("Vừa (500×350)")
        btn_pre_md.clicked.connect(lambda: self._apply_preset(500, 350))
        r1_layout.addWidget(btn_pre_md)

        btn_pre_lg = QPushButton("Lớn (750×500)")
        btn_pre_lg.clicked.connect(lambda: self._apply_preset(750, 500))
        r1_layout.addWidget(btn_pre_lg)

        btn_pre_full = QPushButton("Toàn khổ ngang (90%)")
        btn_pre_full.clicked.connect(self._apply_full_width)
        r1_layout.addWidget(btn_pre_full)

        r1_layout.addSpacing(20)

        btn_zoom_in = QPushButton("🔍+ Phóng to")
        btn_zoom_in.clicked.connect(lambda: self.view.scale(1.25, 1.25))
        r1_layout.addWidget(btn_zoom_in)

        btn_zoom_out = QPushButton("🔍- Thu nhỏ")
        btn_zoom_out.clicked.connect(lambda: self.view.scale(0.8, 0.8))
        r1_layout.addWidget(btn_zoom_out)

        btn_fit = QPushButton("📐 Vừa màn hình")
        btn_fit.clicked.connect(lambda: self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio))
        r1_layout.addWidget(btn_fit)

        btn_focus = QPushButton("🎯 Tập trung khung")
        btn_focus.clicked.connect(lambda: self.view.centerOn(self.crop_item))
        r1_layout.addWidget(btn_focus)

        r1_layout.addStretch()
        layout.addLayout(r1_layout)

        # Row 2 of controls: Fine-tuning & Save/Cancel
        r2_layout = QHBoxLayout()
        r2_layout.addWidget(QLabel("<b>Căn chỉnh biên:</b>"))

        btn_exp_w = QPushButton("Dãn ngang (+50px)")
        btn_exp_w.clicked.connect(lambda: self._adjust_size(50, 0))
        r2_layout.addWidget(btn_exp_w)

        btn_shk_w = QPushButton("Thu ngang (-50px)")
        btn_shk_w.clicked.connect(lambda: self._adjust_size(-50, 0))
        r2_layout.addWidget(btn_shk_w)

        btn_exp_h = QPushButton("Dãn dọc (+50px)")
        btn_exp_h.clicked.connect(lambda: self._adjust_size(0, 50))
        r2_layout.addWidget(btn_exp_h)

        btn_shk_h = QPushButton("Thu dọc (-50px)")
        btn_shk_h.clicked.connect(lambda: self._adjust_size(0, -50))
        r2_layout.addWidget(btn_shk_h)

        btn_autofit = QPushButton("✨ Tự động bám viền hình (Auto-Fit)")
        btn_autofit.setToolTip("Tự động nhận diện và ôm sát viền hình vẽ, loại bỏ tiêu đề hoặc câu chữ đề bài thừa xung quanh")
        btn_autofit.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: bold;
                padding: 5px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        btn_autofit.clicked.connect(self._auto_fit_to_content)
        r2_layout.addWidget(btn_autofit)

        self.btn_rot_crop = QPushButton("⟳ Xoay ảnh 90°")
        self.btn_rot_crop.setToolTip("Xoay ảnh kết quả 90 độ (nếu hình chụp bị nằm ngang/dọc)")
        self.btn_rot_crop.setStyleSheet("""
            QPushButton {
                background-color: #f0fdf4;
                border: 1px solid #bbf7d0;
                color: #166534;
                font-weight: bold;
                padding: 5px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #dcfce7; }
        """)
        self.btn_rot_crop.clicked.connect(self._toggle_crop_rotation)
        r2_layout.addWidget(self.btn_rot_crop)

        r2_layout.addStretch()

        btn_cancel = QPushButton("Hủy bỏ")
        btn_cancel.setStyleSheet("padding: 7px 18px; font-size: 13px;")
        btn_cancel.clicked.connect(self.reject)
        r2_layout.addWidget(btn_cancel)

        btn_save = QPushButton("✔ Lưu khung cắt")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 7px 22px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        btn_save.clicked.connect(self._save_crop)
        r2_layout.addWidget(btn_save)

        layout.addLayout(r2_layout)

        # Initial label update
        self.update_info_label()

    def _toggle_crop_rotation(self):
        self.crop_rotation = (self.crop_rotation + 90) % 360
        if hasattr(self, "btn_rot_crop"):
            if self.crop_rotation == 0:
                self.btn_rot_crop.setText("⟳ Xoay ảnh 90°")
            else:
                self.btn_rot_crop.setText(f"⟳ Xoay ảnh ({self.crop_rotation}°)")
        self.update_info_label()

    def update_info_label(self, override_pos: Optional[QPointF] = None):
        pos = override_pos if override_pos is not None else self.crop_item.pos()
        rect = self.crop_item.rect()
        x = int(pos.x())
        y = int(pos.y())
        w = int(rect.width())
        h = int(rect.height())
        rot_str = f"  |  🔄 Góc xoay: {self.crop_rotation}°" if self.crop_rotation != 0 else ""
        self.lbl_info.setText(f"📍 Tọa độ: X={x}, Y={y}  |  📐 Kích thước khung: {w} × {h} px{rot_str}  (Ảnh trang: {self.img_w} × {self.img_h} px)")

    def center_crop_at(self, pt: QPointF):
        r = self.crop_item.rect()
        new_x = max(0.0, min(self.img_w - r.width(), pt.x() - r.width() / 2.0))
        new_y = max(0.0, min(self.img_h - r.height(), pt.y() - r.height() / 2.0))
        self.crop_item.setPos(new_x, new_y)
        self.update_info_label()

    def _apply_preset(self, w: int, h: int):
        pos = self.crop_item.pos()
        cur_r = self.crop_item.rect()
        cx = pos.x() + cur_r.width() / 2.0
        cy = pos.y() + cur_r.height() / 2.0

        new_w = min(float(self.img_w), float(w))
        new_h = min(float(self.img_h), float(h))
        new_x = max(0.0, min(self.img_w - new_w, cx - new_w / 2.0))
        new_y = max(0.0, min(self.img_h - new_h, cy - new_h / 2.0))

        self.crop_item.setPos(new_x, new_y)
        self.crop_item.setRect(0, 0, new_w, new_h)
        self.update_info_label()

    def _apply_full_width(self):
        new_w = self.img_w * 0.90
        new_x = self.img_w * 0.05
        cur_r = self.crop_item.rect()
        self.crop_item.setPos(new_x, self.crop_item.pos().y())
        self.crop_item.setRect(0, 0, new_w, cur_r.height())
        self.update_info_label()

    def _adjust_size(self, dw: int, dh: int):
        cur_r = self.crop_item.rect()
        pos = self.crop_item.pos()
        new_w = max(30.0, min(self.img_w - pos.x(), cur_r.width() + dw))
        new_h = max(30.0, min(self.img_h - pos.y(), cur_r.height() + dh))
        self.crop_item.setRect(0, 0, new_w, new_h)
        self.update_info_label()

    def _auto_fit_to_content(self):
        """Tự động nhận diện nét vẽ và co khung ôm sát hình học, loại bỏ dòng chữ thừa."""
        try:
            from core.image_cropper import ImageCropper
            pos = self.crop_item.pos()
            r = self.crop_item.rect()
            cur_box = (int(pos.x()), int(pos.y()), int(pos.x() + r.width()), int(pos.y() + r.height()))

            with Image.open(self.image_path) as full_img:
                new_l, new_t, new_r, new_b = ImageCropper.refine_pixel_box(full_img, cur_box)

            self.crop_item.setPos(float(new_l), float(new_t))
            self.crop_item.setRect(0, 0, float(new_r - new_l), float(new_b - new_t))
            self.update_info_label()
        except Exception as e:
            QMessageBox.warning(self, "Thông báo", f"Không thể tự động bám viền: {str(e)}")

    def _save_crop(self):
        pos = self.crop_item.pos()
        rect = self.crop_item.rect()

        left = max(0, int(pos.x()))
        top = max(0, int(pos.y()))
        right = min(self.img_w, int(left + rect.width()))
        bottom = min(self.img_h, int(top + rect.height()))

        if right - left < 10 or bottom - top < 10:
            QMessageBox.warning(self, "Cảnh báo", "Khung cắt quá nhỏ! Vui lòng mở rộng khung ít nhất 10px.")
            return

        self.result_pixel_box = (left, top, right, bottom)
        self.result_rotation = self.crop_rotation
        self.accept()

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        step = 10 if (modifiers & Qt.KeyboardModifier.ControlModifier) else 2

        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            # Shift + Arrow: Resize width / height
            if key == Qt.Key.Key_Left:
                self._adjust_size(-step, 0)
                return
            elif key == Qt.Key.Key_Right:
                self._adjust_size(step, 0)
                return
            elif key == Qt.Key.Key_Up:
                self._adjust_size(0, -step)
                return
            elif key == Qt.Key.Key_Down:
                self._adjust_size(0, step)
                return
        else:
            # Arrow alone: Nudge position
            pos = self.crop_item.pos()
            if key == Qt.Key.Key_Left:
                self.crop_item.setPos(pos.x() - step, pos.y())
                self.update_info_label()
                return
            elif key == Qt.Key.Key_Right:
                self.crop_item.setPos(pos.x() + step, pos.y())
                self.update_info_label()
                return
            elif key == Qt.Key.Key_Up:
                self.crop_item.setPos(pos.x(), pos.y() - step)
                self.update_info_label()
                return
            elif key == Qt.Key.Key_Down:
                self.crop_item.setPos(pos.x(), pos.y() + step)
                self.update_info_label()
                return

        super().keyPressEvent(event)

