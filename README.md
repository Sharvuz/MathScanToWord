# MathScanToWord - Công Cụ Số Hóa Sách Scan & Đề Thi Toán Sang Word

Phần mềm Desktop chuyên dụng giúp số hóa sách giáo khoa scan, đề thi và tài liệu học thuật (Toán - KHTN) định dạng PDF hoặc ảnh sang **Microsoft Word (.docx)** với công thức toán chuẩn **OMML / MathType**, tự động bóc tách và định dạng trắc nghiệm theo chuẩn Bộ GD&ĐT, đồng thời nhận diện và cắt hình học thông minh bằng AI (Google Gemini Vision).

---

## 🌟 CÁC TÍNH NĂNG NỔI BẬT

### 1. Số hóa công thức Toán chuẩn Native Word (OMML / MathType)
- Tự động chuyển đổi công thức LaTeX sang **OMML native** của Microsoft Word (hiển thị công thức toán thực thụ, không cần cài đặt thêm MathType vẫn hiển thị và chỉnh sửa trực tiếp được).
- Hỗ trợ chuẩn hóa ngược tương thích 100% với phím tắt **`Alt + \` (Toggle TeX)** của MathType.
- **Deep Math Sanitizer**:
  - Tự động phân biệt và chuẩn hóa gốc tọa độ $O$ vs số 0 ($0xyz \rightarrow Oxyz$, trục $0x \rightarrow Ox$).
  - Chuẩn hóa ký hiệu góc ($\widehat{ABC}$), độ ($60^\circ$).
  - Chuẩn hóa hệ phương trình $\begin{cases} ... \end{cases}$ và hệ tuyển ngoặc vuông.
  - Chuẩn hóa đơn vị đo lường ($m$, $cm$, $km$, $kg$, $s$, $h$,...) tự động chèn khoảng cách đẹp mắt, loại bỏ triệt để rác OCR.

### 2. Tự động nhận diện & bóc tách bố cục 2 cột dọc (Two-Column Splitter)
- Tự động phân tích hình ảnh trang tài liệu bằng OpenCV để phát hiện vách ngăn giữa 2 cột (hoặc dải khoảng trắng phân cách).
- Cắt trang thành Nửa Trái $\rightarrow$ Nửa Phải, bóc tách tuần tự đảm bảo **100% không bị nhảy câu hay đọc ngang dòng**.

### 3. Cắt hình ảnh & Đồ thị thông minh (Smart Contour Auto-Snap & Blank Rejector)
- **Hút viền nét vẽ tự động (Contour Snapping)**: Tự động phân tích thành phần liên thông (Connected Components) quanh bounding box, tự động ôm khít hình vẽ, không cắt lẹm đỉnh hình học ($A, B, C$) và không dính chữ đề bài.
- **Bộ lọc hình rỗng (Blank Rejector)**: Tự động nhận diện và loại bỏ các khung hình bị cắt nhầm mà bên trong chỉ toàn khoảng trắng hoặc hạt nhiễu, tránh chèn hình rác vào Word.
- Hỗ trợ công cụ **Xem lại & Chỉnh khung cắt hình ảnh** trực quan bằng chuột trước khi chèn vào Word.

### 4. Định dạng trắc nghiệm thông minh chuẩn Bộ GD&ĐT (Smart Fluid Layout)
- Tự động nhận diện câu hỏi trắc nghiệm 4 phương án $A, B, C, D$.
- Tự động căn chỉnh bảng ẩn (borderless table) theo chuẩn quy cách:
  - **1 dòng 4 cột**: Khi các phương án ngắn.
  - **2 dòng 2 cột**: Khi các phương án có độ dài trung bình.
  - **4 dòng 1 cột**: Khi các phương án là câu dài/lời giải.
- Đặt câu hỏi và hình minh họa nằm song song (Câu hỏi bên trái - Hình vẽ bên phải) tự nhiên như đề thi chính thức.
- Tự động phát hiện và gạch chân đáp án đúng (tương thích đề thi McMix / SmartTest).

### 5. Quản lý đa luồng & Xoay tua API Key (Multi-Key Affinity Pool)
- Hỗ trợ cấu hình cùng lúc nhiều Google Gemini API Key.
- Phân luồng xử lý song song nhiều trang (Concurrent Workers) với cơ chế gán key theo luồng (Thread-Key Affinity), tránh lỗi xung đột giới hạn tốc độ (Rate Limit 429).
- Tự động chuyển key khi mạng chậm hoặc chạm hạn mức.
- Tự động vượt bộ lọc bản quyền (Google Recitation Filter) bằng chế độ bóc tách chia nửa trang (Halved-Page Fallback).
- Bộ đệm Checkpointing cuốn chiếu: Không bao giờ mất dữ liệu nếu gặp sự cố hoặc dừng giữa chừng.

---

## 🚀 HƯỚNG DẪN CÀI ĐẶT & CHẠY TRÊN MÁY MỚI

### Yêu cầu hệ thống
- Hệ điều hành: Windows 10/11 (khuyên dùng), macOS, hoặc Linux.
- Python: **Phiên bản 3.10 - 3.12**.
- Microsoft Office Word (nếu muốn xem và chỉnh sửa trực tiếp file `.docx`).

### Các bước cài đặt:

1. **Tải mã nguồn (Clone repository)**:
   ```bash
   git clone git@github.com:Sharvuz/MathScanToWord.git
   cd MathScanToWord
   ```
   *(Hoặc tải file ZIP về giải nén và mở thư mục trong Terminal)*.

2. **Tạo môi trường ảo và cài đặt thư viện**:
   - Trên **Windows**:
     ```powershell
     python -m venv .venv
     .venv\Scripts\activate
     pip install -r requirements.txt
     ```
   - Trên **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     pip install -r requirements.txt
     ```

3. **Cấu hình API Key**:
   - Nhân bản file `config.example.json` thành `config.json`:
     ```bash
     cp config.example.json config.json
     ```
   - Mở `config.json` và điền ít nhất 1 (khuyên dùng 3) Google Gemini API Key miễn phí lấy từ [Google AI Studio](https://aistudio.google.com/):
     ```json
     {
       "api_keys": [
         "AIzaSyYourFirstApiKeyHere...",
         "AIzaSyYourSecondApiKeyHere..."
       ]
     }
     ```
   *(Lưu ý: Bạn cũng có thể mở giao diện phần mềm rồi nhập API Key trực tiếp vào tab Cấu hình mà không cần sửa file JSON).*

4. **Khởi chạy ứng dụng**:
   - Cách 1: Nhấp đúp chuột vào file **`CHAY_TOOL_GIAO_DIEN.bat`** (trên Windows).
   - Cách 2: Chạy lệnh:
     ```bash
     python app.py
     ```

---

## 📂 CẤU TRÚC DỰ ÁN

```
MathScanToWord/
├── core/
│   ├── gemini_engine.py       # Engine giao tiếp Google Gemini API, xoay tua key, chống Recitation
│   ├── image_cropper.py       # Bóc tách hình ảnh, Contour Snapping & Blank Rejector
│   ├── image_preprocessor.py  # Xử lý ảnh OpenCV, tẩy trắng nền, nhận diện 2 cột dọc
│   ├── latex_formatter.py     # Chuẩn hóa công thức Toán chuyên sâu, dọn rác OCR
│   ├── mcmix_formatter.py     # Định dạng tương thích McMix, trích xuất bảng đáp án
│   ├── omml_converter.py      # Bộ chuyển đổi LaTeX -> MathML -> Word OMML native
│   ├── pdf_processor.py       # Render trang PDF 250-300 DPI, chia nhỏ PDF
│   ├── word_builder.py        # Dựng tài liệu Word (.docx), bố cục trắc nghiệm & hình vẽ
│   └── cache_manager.py       # Quản lý bộ đệm và lưu trữ cuốn chiếu từng trang
├── gui/
│   ├── main_window.py         # Giao diện chính PyQt6 (Tiến trình, xem trước, cài đặt)
│   ├── review_dialog.py       # Hộp thoại xem lại và chỉnh khung cắt hình học
│   └── split_pdf_tab.py       # Tab chia nhỏ PDF dành cho sách scan dung lượng lớn
├── app.py                     # Entry point khởi chạy giao diện
├── converter_pipeline.py      # Pipeline chạy qua dòng lệnh (CLI / headless mode)
├── CHAY_TOOL_GIAO_DIEN.bat    # Phím tắt nhấp đúp chạy nhanh trên Windows
├── config.example.json        # Mẫu file cấu hình chuẩn
├── requirements.txt           # Danh sách các thư viện phụ thuộc
└── README.md                  # Tài liệu hướng dẫn sử dụng
```

---

## 📄 GIẤY PHÉP (LICENSE)
Dự án được phát hành dưới giấy phép mã nguồn mở MIT. Tự do sử dụng và tùy biến cho mục đích cá nhân và giáo dục.
