import time
import json
import base64
import requests
import io
import re
from typing import List, Dict, Any, Optional, Callable
from PIL import Image

SYSTEM_PROMPT = """Bạn là chuyên gia số hóa tài liệu toán học Việt Nam với độ chính xác tuyệt đối.
Nhiệm vụ của bạn là đọc hình ảnh trang sách toán scan này và trích xuất thành văn bản có công thức toán học chuẩn LaTeX (hỗ trợ MathType Toggle TeX) và nhận diện tọa độ các hình minh họa/hình học/đồ thị.

QUY TẮC CỐT LÕI:
1. ĐỊNH DẠNG VĂN BẢN VÀ CÔNG THỨC TOÁN CHO MATHTYPE:
- VĂN BẢN TIẾNG VIỆT THƯỜNG (Lời dẫn đề bài, câu hỏi, hướng dẫn giải, chọn đáp án):
  Viết tiếng Việt bình thường. TUYỆT ĐỐI KHÔNG bọc các từ tiếng Việt thông thường vào trong \\text{...} (ví dụ: TUYỆT ĐỐI KHÔNG viết \\text{Câu}, \\text{Tam giác}, \\text{Chọn}, \\text{Áp dụng}, \\text{Giá trị}).
  TUYỆT ĐỐI KHÔNG bọc cả câu văn vào trong dấu $...$.
- CÔNG THỨC TOÁN HỌC: MỌI biểu thức, phương trình, số đo, phân số, đáp án trắc nghiệm BẮT BUỘC nằm trong $...$ (nội dòng) hoặc $$...$$ (khối riêng).
  Ví dụ: Viết A. $\\dfrac{\\sqrt{55}}{2}$, TUYỆT ĐỐI KHÔNG viết cộc lốc A. \\frac{\\sqrt{55}}{2}.
  \\text{...} CHỈ ĐƯỢC PHÉP DÙNG khi nằm bên trong $...$ cho đơn vị đo hoặc chú thích (ví dụ: $S_{\\text{tam giác}}$, $V = 10\\text{ cm}^3$, $\\text{tuổi của Bình}$, $2{,}5\\text{ mét}$).
- KÝ HIỆU HÌNH HỌC & ĐIỂM: Các đỉnh, cạnh, tam giác (A, B, C, K, M, N, AB, BC, AH, \\Delta ABC) là biến toán học, VIẾT TRỰC TIẾP LÀ $A$, $B$, $K$, $BC$, $\\Delta ABC$.
- KÝ TỰ Ô VUÔNG RỖNG: Nếu trang scan có ô vuông rỗng do lỗi font scan (như [□; 2] hoặc M(□; ...)), hãy khôi phục đúng ký tự toán học (như dấu trừ $[-1; 2]$) hoặc loại bỏ ô vuông vô nghĩa.
- BÀI TOÁN THỰC TẾ & LỜI VĂN DÀI: Với các bài toán có nhiều câu văn hoặc dữ kiện số đo, hãy trình bày cấu trúc mạch lạc, mỗi câu văn hoặc số liệu đo lường viết trên một dòng riêng biệt, công thức và số đo bọc trong $...$. Điều này giúp tài liệu sư phạm sáng sủa và không bị dính khối văn bản.
- Dùng \\dfrac{...}{...} cho phân số, \\begin{cases} ... \\end{cases} cho hệ phương trình.
- Góc dùng \\widehat{ABC}, vectơ dùng \\vec{a} hoặc \\overrightarrow{AB}.

2. BẢNG BIỂU (BẢNG ĐÁP ÁN, HƯỚNG DẪN CHẤM, BẢNG BIẾN THIÊN):
- Định dạng chuẩn bảng Markdown: | Cột 1 | Cột 2 | Cột 3 | kèm dòng gạch ngang |---|---|---|.
- Xuống dòng bên trong ô của bảng: dùng thẻ <br>.

3. NHẬN DIỆN VÀ TỌA ĐỘ HÌNH VẼ / HÌNH HỌC / ĐỒ THỊ:
- KHÔNG vẽ lại hình bằng ASCII hay TikZ.
- Xác định tọa độ Bounding Box box_2d theo thang đo 0 đến 1000: [ymin, xmin, ymax, xmax].
- NGUYÊN TẮC CẮT HÌNH CHÍNH XÁC:
  + Tọa độ BẮT BUỘC CHỈ ÔM SÁT HÌNH VẼ / ĐỒ THỊ / HÌNH HỌC VÀ CÁC ĐIỂM ĐỈNH (A, B, C...).
  + TUYỆT ĐỐI KHÔNG CHỨA DÒNG TIÊU ĐỀ TRANG (như tên trường, số trang, tiêu đề 'Bộ đề ôn...', đường kẻ phân cách ở mép trên).
  + TUYỆT ĐỐI KHÔNG CẮT DÍNH DÒNG CHỮ ĐỀ BÀI Ở TRÊN HOẶC DƯỚI HÌNH (như 'Đoạn thẳng PQ', 'Cho tam giác...', 'chứa 5 viên bi...').
  + Đặt đúng thẻ [HINH_1], [HINH_2],... vào ngay bên dưới câu hỏi/bài toán có hình đó.

4. TƯƠNG THÍCH TRỘN ĐỀ THI & ĐÁP ÁN TRẮC NGHIỆM:
- Các phương án trắc nghiệm viết chuẩn dạng A., B., C., D.
- Nếu đề thi có đánh dấu đáp án đúng (gạch chân, khoanh tròn, in đậm, hoặc dấu * ở chữ cái đáp án), hãy biểu thị bằng thẻ <u>A.</u> hoặc <u>B.</u> để phần mềm trộn đề (McMix, SmartTest) tự động nhận diện.
- Nếu đề có ghi sẵn mức độ [NB], [TH], [VD], [VDC], hãy giữ nguyên vẹn tag đó ở đầu mỗi câu hỏi.

5. ĐỊNH DẠNG ĐẦU RA (OUTPUT FORMAT):
Chỉ trả về DUY NHẤT một chuỗi JSON hợp lệ với cấu trúc sau:
{
  "figures": [
    {
      "id": "HINH_1",
      "box_2d": [ymin, xmin, ymax, xmax],
      "description": "Mô tả ngắn gọn về hình vẽ"
    }
  ],
  "markdown": "Toàn bộ nội dung văn bản và công thức toán học của trang, chứa các thẻ [HINH_1] đúng vị trí..."
}"""

class GeminiEngine:
    def __init__(
        self,
        api_keys: List[str],
        model: str = "gemini-flash-latest",
        slow_threshold_seconds: float = 15.0,
        log_callback: Optional[Callable[[str, str], None]] = None
    ):
        self.api_keys = [k.strip() for k in api_keys if k.strip()]
        self.model = model
        self.slow_threshold = slow_threshold_seconds
        self.log_callback = log_callback or (lambda msg, level: None)
        self.current_key_idx = 0

    def log(self, message: str, level: str = "info"):
        """level can be 'info' (green/white), 'warning' (orange), 'error' (red), 'debug' (blue)"""
        now_str = time.strftime("[%H:%M:%S]")
        formatted = f"{now_str} {message}"
        self.log_callback(formatted, level)

    def get_current_key(self) -> str:
        if not self.api_keys:
            raise ValueError("Không có API Key nào được cấu hình!")
        return self.api_keys[self.current_key_idx]

    def rotate_to_next_key(self, reason: str = ""):
        if len(self.api_keys) <= 1:
            return
        old_idx = self.current_key_idx
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        self.log(
            f"{reason} Chuyển từ API {old_idx + 1} sang API {self.current_key_idx + 1}.",
            "warning"
        )

    def process_page_image(self, image: Image.Image, page_num: int, preferred_key_idx: Optional[int] = None) -> Dict[str, Any]:
        """
        Sends page image to Gemini with auto-retry and multi-key rotation.
        Supports preferred_key_idx for thread-safe concurrent execution across multiple keys!
        Returns a dict with 'markdown' and 'figures'.
        """
        # Convert image to JPEG/PNG bytes
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=90)
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        max_attempts = max(6, len(self.api_keys) * 3)
        attempt = 0
        local_key_idx = (preferred_key_idx if preferred_key_idx is not None else self.current_key_idx) % len(self.api_keys)
        use_anti_recitation = False
        recitation_count = 0

        while attempt < max_attempts:
            attempt += 1
            key = self.api_keys[local_key_idx]
            key_num = local_key_idx + 1

            mode_str = " (Chống Recitation)" if use_anti_recitation else ""
            self.log(
                f"[Trang {page_num}] Đang xử lý bằng API {key_num} với model {self.model}{mode_str}...",
                "info"
            )
            start_time = time.time()

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": key
            }

            if not use_anti_recitation:
                user_prompt = (
                    f"Hãy đọc và số hóa trang sách toán số {page_num} này theo quy tắc JSON đã nêu. "
                    f"Trình bày các bài toán thực tế rõ ràng, bọc các đại lượng và số đo trong $...$."
                )
            else:
                user_prompt = (
                    f"Hãy số hóa trang đề thi toán số {page_num} này thành JSON: {{\"markdown\": string, \"figures\": []}}. "
                    f"Quy tắc quan trọng: Với các bài toán thực tế có lời văn, hãy trình bày cấu trúc rõ ràng: "
                    f"mỗi câu văn hoặc số liệu đo lường viết trên một dòng riêng biệt, công thức bọc trong $...$. "
                    f"Gắn thẻ [HINH_X] tương ứng vị trí các hình vẽ."
                )

            payload = {
                "systemInstruction": {
                    "parts": [{"text": SYSTEM_PROMPT}]
                },
                "contents": [
                    {
                        "parts": [
                            {"text": user_prompt},
                            {
                                "inlineData": {
                                    "mimeType": "image/jpeg",
                                    "data": img_base64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1
                }
            }

            try:
                # 45-second HTTP timeout
                response = requests.post(url, headers=headers, json=payload, timeout=45)
                elapsed = time.time() - start_time

                if response.status_code == 200:
                    resp_json = response.json()
                    candidates = resp_json.get("candidates", [])
                    if not candidates:
                        prompt_feedback = resp_json.get("promptFeedback", {})
                        block_reason = prompt_feedback.get("blockReason", "Nội dung bị chặn")
                        self.log(f"[Trang {page_num}] Google API chặn yêu cầu ({block_reason}).", "warning")
                        local_key_idx = (local_key_idx + 1) % len(self.api_keys)
                        time.sleep(2)
                        continue

                    cand = candidates[0]
                    finish_reason = cand.get("finishReason", "")
                    content = cand.get("content", {})
                    parts = content.get("parts", [])

                    if not parts:
                        if finish_reason == "RECITATION":
                            recitation_count += 1
                            self.log(
                                f"[Trang {page_num}] ⚠️ Phát hiện bộ lọc bản quyền Google (Recitation Filter). Đang tự động kích hoạt chế độ bóc tách chống Recitation...",
                                "warning"
                            )
                            use_anti_recitation = True
                            if recitation_count >= 2:
                                self.log(
                                    f"[Trang {page_num}] ✂ Tự động chia nửa trang (Top/Bottom) để vượt triệt để bộ lọc Recitation...",
                                    "info"
                                )
                                return self._process_halved_page(image, page_num, local_key_idx)
                            time.sleep(1)
                            continue
                        elif finish_reason == "SAFETY":
                            self.log(f"[Trang {page_num}] ⚠️ Google API từ chối do chính sách an toàn (SAFETY).", "error")
                            local_key_idx = (local_key_idx + 1) % len(self.api_keys)
                            time.sleep(2)
                            continue
                        else:
                            self.log(f"[Trang {page_num}] API phản hồi không có nội dung (finishReason: {finish_reason}).", "warning")
                            local_key_idx = (local_key_idx + 1) % len(self.api_keys)
                            time.sleep(2)
                            continue

                    raw_text = parts[0].get("text", "")
                    
                    self.log(
                        f"[Trang {page_num}] Chuyển đổi thành công bằng API {key_num} với model {self.model} ({elapsed:.1f} giây).",
                        "success"
                    )

                    # Check if response was unusually slow (> threshold)
                    if elapsed >= self.slow_threshold and len(self.api_keys) > 1:
                        self.rotate_to_next_key(f"[Trang {page_num}] Mất {elapsed:.1f}s - chậm hơn bình thường (ngưỡng {self.slow_threshold}s).")

                    # Parse JSON
                    return self._clean_and_parse_json(raw_text)

                elif response.status_code == 429:
                    self.log(f"[Trang {page_num}] API {key_num} chạm hạn mức (Error 429: Too Many Requests).", "warning")
                    local_key_idx = (local_key_idx + 1) % len(self.api_keys)
                    wait_time = min(15.0, 3.0 * attempt)
                    self.log(f"[Trang {page_num}] Chuyển sang API {local_key_idx + 1}, tạm dừng {wait_time:.1f}s để hồi hạn mức...", "info")
                    time.sleep(wait_time)
                else:
                    self.log(f"[Trang {page_num}] API {key_num} báo lỗi HTTP {response.status_code}: {response.text[:120]}", "error")
                    local_key_idx = (local_key_idx + 1) % len(self.api_keys)
                    time.sleep(2)

            except requests.exceptions.Timeout:
                self.log(f"[Trang {page_num}] API {key_num} quá thời gian chờ (Timeout sau 45s).", "error")
                local_key_idx = (local_key_idx + 1) % len(self.api_keys)
            except Exception as e:
                self.log(f"[Trang {page_num}] Lỗi xử lý API {key_num}: {str(e)}", "error")
                local_key_idx = (local_key_idx + 1) % len(self.api_keys)
                time.sleep(2)

        raise RuntimeError(f"Không thể xử lý trang {page_num} sau nhiều lần thử với tất cả API keys.")

    def _process_halved_page(self, image: Image.Image, page_num: int, preferred_key_idx: int) -> Dict[str, Any]:
        """
        Chia trang theo chiều dọc (Top half / Bottom half) để vượt qua bộ lọc Recitation.
        Tự động mapping tọa độ box_2d của nửa dưới về tọa độ 0..1000 của toàn trang.
        """
        w, h = image.size
        split_y = int(h * 0.50)
        top_img = image.crop((0, 0, w, min(h, split_y + 15)))
        bot_img = image.crop((0, max(0, split_y - 15), w, h))

        self.log(f"[Trang {page_num}] 📖 Đang bóc tách Nửa trên...", "info")
        resp_top = self.process_page_image(top_img, page_num, preferred_key_idx=preferred_key_idx)

        self.log(f"[Trang {page_num}] 📖 Đang bóc tách Nửa dưới...", "info")
        resp_bot = self.process_page_image(bot_img, page_num, preferred_key_idx=preferred_key_idx)

        md_top = resp_top.get("markdown", "").strip()
        md_bot = resp_bot.get("markdown", "").strip()
        figs_top = resp_top.get("figures", [])
        figs_bot = resp_bot.get("figures", [])

        # Map y coordinates of bottom figures
        h_bot = h - max(0, split_y - 15)
        y_offset_px = max(0, split_y - 15)

        mapped_figs_bot = []
        top_count = len(figs_top)
        for idx, fig in enumerate(figs_bot, 1):
            old_id = fig.get("id", f"HINH_{idx}")
            new_id = f"HINH_{top_count + idx}"
            fig["id"] = new_id
            md_bot = md_bot.replace(f"[{old_id}]", f"[{new_id}]")

            ymin, xmin, ymax, xmax = fig.get("box_2d", [0, 0, 1000, 1000])
            ymin_px = y_offset_px + (ymin / 1000.0) * h_bot
            ymax_px = y_offset_px + (ymax / 1000.0) * h_bot
            fig["box_2d"] = [
                min(1000, max(0, (ymin_px / h) * 1000.0)),
                xmin,
                min(1000, max(0, (ymax_px / h) * 1000.0)),
                xmax
            ]
            mapped_figs_bot.append(fig)

        combined_md = f"{md_top}\n\n{md_bot}" if md_top and md_bot else (md_top or md_bot)
        combined_figs = figs_top + mapped_figs_bot

        self.log(f"[Trang {page_num}] ✅ Đã ghép nối thành công 2 nửa trang ({len(combined_figs)} hình vẽ).", "success")
        return {
            "markdown": combined_md,
            "figures": combined_figs
        }

    @staticmethod
    def _fix_json_latex_escapes(text: str) -> str:
        r"""
        Fixes unescaped LaTeX commands in JSON strings where single backslashes collide
        with standard JSON escape codes (\t, \f, \b, \r, \n).
        Without this, \text becomes \x09ext (TAB + 'ext'), \frac becomes \x0crac (FF + 'rac'), etc.
        """
        latex_cmds = (
            r'text|textbf|textit|texttt|tfrac|tan|tanh|theta|times|to|tau|top|triangle|'
            r'dfrac|frac|forall|'
            r'bar|beta|begin|binom|mathbf|boldsymbol|bullet|bot|'
            r'right|rho|rangle|rightarrow|Rightarrow|'
            r'neq|nabla|neg|notin'
        )
        pattern = rf'(?<!\\)\\({latex_cmds})\b'
        return re.sub(pattern, r'\\\\\1', text)

    def _clean_and_parse_json(self, raw_text: str) -> Dict[str, Any]:
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Fix unescaped LaTeX commands before json.loads so \t, \f, \b etc. are not eaten
        cleaned = self._fix_json_latex_escapes(cleaned)

        # 1. Try standard json.loads first
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return {
                    "markdown": data.get("markdown", ""),
                    "figures": data.get("figures", [])
                }
        except Exception:
            pass

        # 2. Advanced regex parser for unescaped LaTeX backslashes (\dfrac, \left, etc.)
        figures = []
        fig_match = re.search(r'"figures"\s*:\s*(\[\s*\{.*?\}\s*\])', cleaned, flags=re.DOTALL)
        if fig_match:
            try:
                figures = json.loads(fig_match.group(1))
            except Exception:
                pass

        md_text = ""
        md_match = re.search(r'"markdown"\s*:\s*"(.*)"\s*\}\s*$', cleaned, flags=re.DOTALL)
        if md_match:
            md_text = md_match.group(1)
            md_text = md_text.replace(r'\n', '\n').replace(r'\"', '"')
            return {"markdown": md_text, "figures": figures}

        # Fallback if model returned plain text instead of strict JSON
        return {
            "markdown": raw_text,
            "figures": []
        }

