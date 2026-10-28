import sys
import os
import traceback

def main():
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        from gui.main_window import MainWindow

        # Enable high DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        window = MainWindow()
        window.show()

        sys.exit(app.exec())
    except Exception as e:
        err_msg = traceback.format_exc()
        try:
            with open("startup_error.log", "w", encoding="utf-8") as f:
                f.write(err_msg)
        except Exception:
            pass

        # Hiển thị thông báo lỗi trực tiếp trên màn hình Windows
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Không thể khởi động MathScanToWord:\n\n{str(e)}\n\nChi tiết lỗi đã được lưu vào file startup_error.log.",
                "Lỗi Khởi Động Ứng Dụng",
                0x10  # MB_ICONERROR
            )
        except Exception:
            print("LỖI KHỞI ĐỘNG:", err_msg, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
