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

### 3. Cắt hình ảnh & AI vẽ lại hình học trực diện (AI Geometry Artist & Smart Snapping)
- **Họa sĩ AI vẽ lại hình học (AI Geometry Artist)**:
  - Tự động phát hiện và sử dụng AI sinh mã Matplotlib tái tạo hình vẽ trực diện, phẳng 2D hoặc phối cảnh 3D độ phân giải cao 300 DPI chuẩn sách giáo khoa.
  - **Quy chuẩn Hình học không gian 3D**: Tuân thủ nghiêm ngặt quy ước Bộ GD&ĐT — TẤT CẢ các cạnh khuất bên trong hoặc mặt sau vẽ bằng nét đứt (`--`), cạnh nhìn thấy vẽ nét liền (`-`), chân đường cao có ký hiệu góc vuông 3D.
  - **Quy chuẩn Đồ thị hàm số**: Trục $Ox, Oy$ có mũi tên nhọn, tiệm cận vẽ nét đứt, đánh dấu điểm cực trị và đường gióng tọa độ.
  - Hỗ trợ nút bật/tắt linh hoạt giữa ảnh gốc scan và hình vẽ vector AI.
- **Hút viền nét vẽ tự động (Contour Snapping)**: Tự động phân tích thành phần liên thông (Connected Components) quanh bounding box, tự động ôm khít hình vẽ, không cắt lẹm đỉnh hình học ($A, B, C$) và không dính chữ đề bài.
- **Bộ lọc hình rỗng (Blank Rejector)**: Tự động nhận diện và loại bỏ các khung hình bị cắt nhầm mà bên trong chỉ toàn khoảng trắng hoặc hạt nhiễu, tránh chèn hình rác vào Word.
- Hỗ trợ công cụ **Xem lại & Chỉnh khung cắt hình ảnh** trực quan bằng chuột trước khi chèn vào Word.

### 4. Tự động nắn thẳng ảnh chụp điện thoại (Mobile Photo Dewarping)
- Tự động phát hiện góc chụp nghiêng, méo phối cảnh hình thang và viền đen mặt bàn bằng thuật toán **4-point perspective warp** của OpenCV.
- Tự động nắn thẳng trang giấy về góc nhìn trực diện 90°, tẩy trắng nền giấy và làm nét chữ trước khi chuyển giao cho AI nhận diện.

### 5. Hàng đợi xử lý hàng loạt nhiều file (Batch Processing Queue)
- Cho phép chọn hoặc kéo thả **hàng loạt file PDF và file ảnh** (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`) cùng một lúc vào giao diện.
- Hệ thống tự động xếp hàng và xử lý tuần tự từng file, xuất các file Word tương ứng vào thư mục `output/` mà không cần người dùng thao tác thủ công từng file.

### 6. Định dạng trắc nghiệm thông minh chuẩn Bộ GD&ĐT (Smart Fluid Layout)
- Tự động nhận diện câu hỏi trắc nghiệm 4 phương án $A, B, C, D$.
- Tự động căn chỉnh bảng ẩn (borderless table) theo chuẩn quy cách:
  - **1 dòng 4 cột**: Khi các phương án ngắn.
  - **2 dòng 2 cột**: Khi các phương án có độ dài trung bình.
  - **4 dòng 1 cột**: Khi các phương án là câu dài/lời giải.
- Đặt câu hỏi và hình minh họa nằm song song (Câu hỏi bên trái - Hình vẽ bên phải) tự nhiên như đề thi chính thức.
- Tự động phát hiện và gạch chân đáp án đúng (tương thích đề thi McMix / SmartTest).

### 7. Tùy chọn Fit file tối ưu tiết kiệm giấy in (Compact Paper-Saving Mode)
- **Căn lề siêu hẹp (Narrow Margins)**: Lề trên 0.8cm, lề dưới 0.6cm, lề trái 0.7cm, lề phải 0.8cm (mở rộng chiều rộng in từ 17cm lên 19.5cm, tăng thêm 15% diện tích trình bày).
- **Cỡ chữ 11pt & Giãn dòng tinh gọn**: Sử dụng font chữ thanh thoát (Palatino Linotype / Times New Roman 11pt), giãn dòng 1.15 và khoảng cách đoạn 1pt giúp bố cục vừa vặn như đề thi thật.
- **Dòng chảy liên tục (Continuous Flow)**: Loại bỏ các ngắt trang cứng (`Page Break`) nhân tạo giữa các trang scan, tránh tạo ra các khoảng trắng khổng lồ cuối trang, dồn nội dung bài thi khít khao nhất.
- **Gom ý tự luận lên cùng hàng (Sub-question Compaction)**: Tự động gom các ý `a), b)` và `c), d)` lên cùng 1 hàng bằng bảng ẩn 2 cột, tiết kiệm 50% chiều cao trang giấy.
- **Bảng điểm & Tiêu đề thích ứng**: Bảng tiêu đề đề thi và bảng đáp án (`Câu | Đáp án | Điểm`) tự động mở rộng lấp đầy khổ lề 19.5cm, không bị tràn dòng.

### 8. Quản lý đa luồng & Xoay tua API Key (Multi-Key Affinity Pool)
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

### Cách 1: Khởi chạy 1-Click tự động trên máy mới (Khuyên dùng khi clone repo)
1. **Clone mã nguồn về máy**:
   ```bash
   git clone https://github.com/Sharvuz/MathScanToWord.git
   cd MathScanToWord
   ```
2. **Khởi chạy cực đơn giản**:
   - Nhấp đúp chuột vào file **`CHAY_TOOL_GIAO_DIEN.bat`**.
   - File `.bat` sẽ tự động phát hiện máy mới, tự tạo môi trường ảo `.venv`, tự cài đặt toàn bộ thư viện cần thiết (`requirements.txt`) và mở giao diện phần mềm lên.
   - Bạn chỉ cần nhập Google Gemini API Key vào tab **Cấu hình API & Keys** là dùng được ngay!

---

### Cách 2: Bản Portable độc lập (.EXE) không cần cài Python
Nếu máy ở trung tâm/trường học không có Python và bạn không muốn cài đặt thêm môi trường:
1. Bạn có thể tự đóng gói bản Portable trên máy chính bằng cách nhấp đúp file **`DONG_GOI_PORTABLE_EXE.bat`**.
2. Thư mục độc lập sẽ được tạo tại `dist\MathScanToWord\`.
3. Chỉ cần nén thư mục này thành file `.zip` hoặc copy sang USB, mang sang bất kỳ máy tính Windows nào cũng có thể nhấp đúp vào `MathScanToWord.exe` để chạy trực tiếp 100%!

---

### Cách 3: Cài đặt thủ công bằng dòng lệnh (Dành cho nhà phát triển)
1. **Tạo môi trường ảo và cài đặt thư viện**:
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

2. **Cấu hình API Key**:
   - Nhân bản file `config.example.json` thành `config.json`:
     ```bash
     copy config.example.json config.json
     ```
   - Điền Google Gemini API Key vào `config.json` hoặc nhập trực tiếp trên giao diện ứng dụng.

3. **Chạy ứng dụng**:
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
