import os
import sys
import re
import json
import base64
import time
import subprocess
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import requests

class AIGeometryArtist:
    """
    Chuyên gia AI tái tạo và vẽ lại hình học phẳng & trực diện (2D Vector Geometry Re-creation).
    Chuyển đổi hình vẽ scan bị mờ, méo, lem mực thành hình vẽ đồ họa vector siêu nét:
    - Đường nét xanh navy (#1A237E), linewidth=2.
    - Đỉnh chấm tròn đỏ rực (#D32F2F).
    - Góc vuông có ô vuông xám nhạt (#CCCCCC) viền mảnh (#555555).
    - Tên đỉnh in nghiêng toán học ($A, B, C...$), to rõ ngoài đỉnh.
    - Nền trắng tinh khiết 100%, xuất ảnh 300 DPI.
    """

    GEOMETRY_KEYWORDS = [
        "tam giác", "tứ giác", "hình vuông", "hình chữ nhật", "hình thoi", "hình thang",
        "đường tròn", "hình tròn", "đồ thị", "hệ trục", "tọa độ", "oxy", "0xy", "oxyz",
        "hình chóp", "hình lăng trụ", "hình nón", "hình trụ", "hình cầu",
        "góc", "đường cao", "trung tuyến", "phân giác", "song song", "vuông góc",
        "tiếp tuyến", "dây cung", "cung tròn", "hình học", "vectơ", "vector"
    ]

    @classmethod
    def is_likely_geometry(cls, description: str = "", context_text: str = "") -> bool:
        """
        Xác định xem hình vẽ có phải là hình học (cần vẽ lại) hay là ảnh chụp minh họa đời thực.
        """
        combined = f"{description} {context_text}".lower()
        # Tránh các ảnh minh họa đời thực thuần túy như tranh chân dung, tượng đài, phong cảnh
        if any(term in combined for term in ["chân dung", "tổng thống", "núi rushmore", "phong cảnh", "bản đồ địa lý"]):
            return False
        
        return any(kw in combined for kw in cls.GEOMETRY_KEYWORDS)

    @classmethod
    def redraw_figure(
        cls,
        image_path: str,
        output_path: str,
        api_keys: List[str],
        model: str = "gemini-2.5-flash",
        description: str = "",
        context_text: str = "",
        timeout_seconds: int = 35
    ) -> Optional[str]:
        """
        Gửi ảnh crop và ngữ cảnh cho Gemini để sinh mã Python (Matplotlib),
        sau đó tự động thực thi sinh file ảnh vector PNG 300 DPI siêu nét.
        Trả về output_path nếu thành công, None nếu thất bại.
        """
        if not os.path.exists(image_path) or not api_keys:
            return None

        # Đọc ảnh crop và chuyển sang Base64
        try:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        except Exception:
            return None

        # Xây dựng prompt chuyên biệt
        context_prompt = ""
        if description or context_text:
            context_prompt = f"\nThông tin mô tả/đề bài liên quan đến hình vẽ này:\n- Mô tả hình: {description}\n- Ngữ cảnh bài toán: {context_text[:500]}\n"

        prompt = (
            "Bạn là chuyên gia đồ họa hình học sư phạm môn Toán Việt Nam.\n"
            "Hãy quan sát hình vẽ đính kèm và kết hợp thông tin bài toán dưới đây để viết một đoạn mã Python "
            "hoàn chỉnh (sử dụng thư viện matplotlib) vẽ lại chính xác 100% hình học/đồ thị này một cách trực diện, "
            "đẹp mắt và sắc nét tuyệt đối theo phong cách chuẩn sách giáo khoa Việt Nam:\n"
            f"{context_prompt}\n"
            "QUY CHUẨN THIẾT KẾ BẮT BUỘC THEO TỪNG THỂ LOẠI:\n"
            "1. NẾU LÀ HÌNH HỌC KHÔNG GIAN 3D (Hình chóp, Lăng trụ, Hình hộp, Nón, Trụ, Cầu...):\n"
            "   - QUY TẮC NÉT ĐỨT / NÉT LIỀN CỐT LÕI:\n"
            "     + TẤT CẢ các cạnh bị che khuất bên trong hoặc ở mặt sau (như cạnh đáy phía sau AB/AD, đường cao nội bộ SO/SH, đường chéo khuất...) "
            "BẮT BUỘC vẽ bằng nét đứt: linestyle='--', color='#1A237E', linewidth=1.8.\n"
            "     + Các cạnh nhìn thấy ở phía trước/bên ngoài vẽ bằng nét liền: linestyle='-', color='#1A237E', linewidth=2.0.\n"
            "   - Góc nhìn phối cảnh 3D trực quan, cân đối; các đỉnh (S, A, B, C, D...) đánh dấu bằng chấm tròn đỏ rực (#D32F2F), s=45, zorder=5.\n"
            "   - Chân đường cao hoặc vị trí vuông góc vẽ ký hiệu góc vuông 3D (hình bình hành nhỏ mô phỏng góc vuông không gian).\n\n"
            "2. NẾU LÀ ĐỒ THỊ HÀM SỐ & HỆ TRỤC TỌA ĐỘ (Oxy, Parabol, Hàm bậc 3, 4, Phân thức...):\n"
            "   - Vẽ hệ trục Ox, Oy vuông góc có mũi tên nhọn ở đầu trục (dùng ax.annotate hoặc ax.arrow).\n"
            "   - Nhãn x ở đầu trục hoành, nhãn y ở đầu trục tung, gốc tọa độ O ở vị trí thoáng, ax.set_aspect('equal') nếu phù hợp.\n"
            "   - Đường tiệm cận đứng, tiệm cận ngang: BẮT BUỘC vẽ bằng nét đứt linestyle='--', color='#D32F2F', linewidth=1.5.\n"
            "   - Đường cong đồ thị vẽ mượt mà, liên tục, color='#1A237E', linewidth=2.2.\n"
            "   - Các điểm cực đại, cực tiểu, giao điểm với trục tọa độ: chấm tròn đỏ/xanh kèm đường gióng tọa độ nét đứt xuống hai trục.\n\n"
            "3. NẾU LÀ HÌNH HỌC PHẲNG 2D (Tam giác, Tứ giác, Đường tròn...):\n"
            "   - Nét vẽ các cạnh/đường tròn: màu xanh navy đậm (#1A237E), linewidth=2.0.\n"
            "   - Tất cả các đỉnh (A, B, C, H...) là chấm tròn đỏ rực (#D32F2F), s=50, zorder=5.\n"
            "   - Góc vuông tại các vị trí vuông góc có ký hiệu ô vuông nhỏ màu xám nhạt (#CCCCCC) viền mảnh (#555555).\n"
            "   - ax.set_aspect('equal'), ax.axis('off').\n\n"
            "4. QUY CÁCH CHUNG & XUẤT ẢNH:\n"
            "   - Tên đỉnh và nhãn số đo ghi bằng ký hiệu toán in nghiêng ($A, B, C, S, O, x, y...$), fontsize=18, fontweight='bold', đặt ở vị trí thoáng ngoài hình.\n"
            "   - Nền trắng tinh khiết 100% (facecolor='white').\n"
            "   - Lưu trực tiếp ra đường dẫn file: TARGET_OUTPUT_PATH với dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none'.\n\n"
            "CHỈ TRẢ VỀ DUY NHẤT một khối mã Python hoàn chỉnh trong ```python ... ```, không thêm bất kỳ văn bản giải thích nào khác."
        )

        # Thử gọi API qua danh sách keys
        for key in api_keys:
            if not key or not key.strip():
                continue
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            headers = {"Content-Type": "application/json", "X-goog-api-key": key.strip()}
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": "image/png", "data": img_b64}}
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.1
                }
            }

            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
                if resp.status_code in (429, 503):
                    time.sleep(2.0)
                    resp = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
                if resp.status_code != 200:
                    continue

                resp_data = resp.json()
                candidates = resp_data.get("candidates", [])
                if not candidates:
                    continue

                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                code_match = re.search(r"```python(.*?)```", text_content, re.DOTALL)
                python_code = code_match.group(1).strip() if code_match else text_content.strip()

                if not python_code or "matplotlib" not in python_code:
                    continue

                # Thay thế đường dẫn lưu file đích
                norm_out_path = os.path.abspath(output_path).replace("\\", "/")
                # Tìm chuỗi savefig và thay đường dẫn
                if "TARGET_OUTPUT_PATH" in python_code:
                    python_code = python_code.replace("TARGET_OUTPUT_PATH", norm_out_path)
                else:
                    python_code = re.sub(
                        r"plt\.savefig\s*\(\s*['\"][^'\"]+['\"]",
                        f"plt.savefig('{norm_out_path}'",
                        python_code
                    )

                # Thực thi mã Python an toàn trong tiến trình con
                success = cls._execute_render_script(python_code, output_path)
                if success and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    return output_path

            except Exception:
                continue

        return None

    @classmethod
    def _execute_render_script(cls, python_code: str, expected_output_path: str) -> bool:
        """
        Thực thi đoạn mã vẽ Matplotlib trong file tạm với timeout an toàn.
        """
        os.makedirs(os.path.dirname(os.path.abspath(expected_output_path)), exist_ok=True)
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as tf:
                temp_file = tf.name
                tf.write(python_code)

            python_exe = sys.executable
            # Gọi tiến trình con
            result = subprocess.run(
                [python_exe, temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=18
            )

            if result.returncode == 0 and os.path.exists(expected_output_path):
                return True
            return False
        except Exception:
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
