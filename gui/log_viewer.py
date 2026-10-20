import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QCheckBox, QLabel
)
from PyQt6.QtGui import QTextCursor, QColor
from PyQt6.QtCore import Qt, pyqtSignal

class LogViewer(QDialog):
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nhật ký tiến trình")
        self.resize(550, 680)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        layout = QVBoxLayout(self)

        # Log text area (Dark theme like in screenshot)
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet("""
            QTextEdit {
                background-color: #0c0d0e;
                color: #d1d5db;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                border: 1px solid #333333;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.text_area)

        # Bottom controls
        bottom_layout = QHBoxLayout()

        self.btn_stop = QPushButton("🛑 Dừng")
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                border: 1px solid #b91c1c;
                padding: 6px 20px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
                border: 1px solid #374151;
            }
        """)
        self.btn_stop.clicked.connect(self._on_stop)
        bottom_layout.addWidget(self.btn_stop)

        bottom_layout.addStretch()

        self.chk_auto_scroll = QCheckBox("Tự động cuộn")
        self.chk_auto_scroll.setChecked(True)
        self.chk_auto_scroll.setStyleSheet("color: #d1d5db; font-weight: 500;")
        bottom_layout.addWidget(self.chk_auto_scroll)

        self.chk_auto_close = QCheckBox("Tự động đóng khi hoàn thành")
        self.chk_auto_close.setChecked(False)
        self.chk_auto_close.setStyleSheet("color: #d1d5db; font-weight: 500;")
        bottom_layout.addWidget(self.chk_auto_close)

        self.btn_close = QPushButton("✕ Đóng")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #ffffff;
                border: 1px solid #4b5563;
                padding: 6px 20px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        self.btn_close.clicked.connect(self.hide)
        bottom_layout.addWidget(self.btn_close)

        layout.addLayout(bottom_layout)

    def append_log(self, message: str, level: str = "info"):
        color_hex = "#38bdf8"  # Cyan default
        if level == "success":
            color_hex = "#22c55e"  # Bright green
        elif level == "warning":
            color_hex = "#f59e0b"  # Amber / orange
        elif level == "error":
            color_hex = "#ef4444"  # Red
        elif level == "white":
            color_hex = "#f3f4f6"

        html_msg = f'<span style="color: {color_hex};">{message}</span><br>'
        self.text_area.moveCursor(QTextCursor.MoveOperation.End)
        self.text_area.insertHtml(html_msg)

        if self.chk_auto_scroll.isChecked():
            self.text_area.moveCursor(QTextCursor.MoveOperation.End)

    def clear_logs(self):
        self.text_area.clear()

    def _on_stop(self):
        self.append_log("[NGƯỜI DÙNG BẤM DỪNG] Đang yêu cầu dừng tiến trình...", "warning")
        self.stop_requested.emit()
