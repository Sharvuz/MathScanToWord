# CÔNG CỤ CHUYỂN PDF/ẢNH SÁCH TOÁN SCAN SANG WORD MATHTYPE (GEMINI AI)

Công cụ desktop chuyên dụng chuyển đổi sách toán scan lớn (đến gần 400 trang) sang Microsoft Word với công thức toán chuẩn MathType (Toggle TeX `Alt + \`), tự động nhận diện và cắt hình học, đồ thị hàm số, và tích hợp cơ chế xoay tua Multi-API Keys của Google Gemini.

---

## 🌟 CÁC TÍNH NĂNG NỔI BẬT

1. **Xoay tua Multi-API Keys (Multi-Key Rotation)**:
   - Hỗ trợ lưu danh sách nhiều Google Gemini API Key.
   - Tự động chuyển đổi sang key tiếp theo khi chạm hạn mức (Error 429) hoặc khi một request phản hồi chậm quá 15 giây.
2. **Xử lý tài liệu scan lớn (~400 trang) & Chống tràn RAM**:
   - Tích hợp công cụ **Chia nhỏ PDF**: Cắt file 400 trang thành từng phần 30 trang hoặc 50 trang theo tùy chọn.
   - Hỗ trợ chọn dải trang linh hoạt (ví dụ: `1-30, 45, 50-70`).
   - Xử lý cuốn chiếu từng trang và lưu bộ nhớ đệm (Cache/Checkpoint). Nếu mất điện hoặc dừng giữa chừng, mở lại sẽ tiếp tục từ trang dở dang mà không mất kết quả cũ.
3. **Nhận diện và cắt hình ảnh (Geometry & Diagram Detection)**:
   - Gemini Vision tự động trả về tọa độ Bounding Box của hình học, đồ thị và chèn thẻ vị trí `[HINH_X]` vào văn bản.
   - Cửa sổ **"Xem lại hình đã nhận diện"**: Cho phép bật/tắt hình ảnh và mở công cụ **"Chỉnh khung"** để kéo thả chỉnh lại vùng cắt nếu AI crop lệch mép.
4. **Chuẩn hóa công thức Toán chuẩn 100% MathType**:
   - Tự động bọc `\text{...}` cho các từ tiếng Việt và đơn vị trong công thức (ví dụ: `$S_{\text{tam giác}}$`, `$\text{ƯCLN}(a;b)$`, `$V = 15\text{ cm}^3$`).
   - Chuẩn hóa dấu phẩy thập phân `{,}` (tránh bị cách chữ).
   - Tương thích 100% với phím tắt **`Alt + \`** (Toggle TeX) của MathType trong Microsoft Word.
5. **Cửa sổ Gemini Log Viewer thời gian thực**:
   - Bảng nhật ký giao diện tối hiển thị rõ từng giây xử lý của từng trang và trạng thái đảo key.

---

## 🚀 HƯỚNG DẪN KHỞI CHẠY

Bạn chỉ cần **nhấp đúp chuột vào file `run.bat`** trong thư mục `C:\Su\TOOL` để mở ứng dụng!

Hoặc chạy lệnh từ cửa sổ Terminal / PowerShell:
```powershell
cd C:\Su\TOOL
.venv\Scripts\python.exe app.py
```

---

## 📖 QUY TRÌNH SỬ DỤNG

1. **Bước 1**: Nhấp đúp chuột vào file **`run.bat`** để mở phần mềm.
2. **Bước 2**: Tại tab **"Cấu hình API & Keys"**, các API key bạn cung cấp đã được lưu sẵn. Bạn có thể thêm key mới bất kỳ lúc nào.
3. **Bước 3**: 
   - Nếu file sách scan quá dày (~400 trang): Chuyển sang tab **"Chia nhỏ PDF"** để cắt file thành các phần nhỏ (mỗi phần 30 trang).
   - Hoặc tại tab chính **"Ảnh, PDF -> WORD"**: Chọn file PDF và nhập dải trang cần làm (ví dụ: `1-30`).
4. **Bước 4**: Bấm nút **"GỬI YÊU CẦU XỬ LÝ (CHUYỂN SANG WORD)"**. Cửa sổ Log Viewer sẽ mở ra hiển thị tiến trình thời gian thực.
5. **Bước 5**: Khi xử lý xong:
   - Bấm **"Xem lại hình đã nhận diện"** để kiểm tra và chỉnh khung hình vẽ nếu cần.
   - Bấm **"Mở file Word"** để mở văn bản `.docx` đã tạo.
   - Trong Microsoft Word, chỉ cần bôi đen văn bản và bấm **`Alt + \`** (Toggle TeX) là toàn bộ công thức chuyển thành MathType hoàn hảo!
