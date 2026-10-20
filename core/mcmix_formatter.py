import re
from typing import Dict, List, Tuple, Optional

class MCMixFormatter:
    """
    Chuẩn hóa cấu trúc câu hỏi và đáp án tương thích 100% với các phần mềm trộn đề thi:
    McMix, Young Mix, SmartTest, Azota.
    
    1. Chuẩn hóa câu hỏi: 'Câu X: [TAG]' (với TAG là [NB], [TH], [VD], [VDC]).
    2. Tự động nhận diện hoặc suy luận Tag nhận thức [NB], [TH], [VD], [VDC].
    3. Tự động bóc tách bảng đáp án (nếu có) và gạch chân đáp án đúng <u>A.</u> để McMix tự động nhận diện.
    """

    TAG_KEYWORDS = {
        "NB": [
            r"bảng biến thiên", r"số điểm cực trị", r"tiệm cận", r"tập xác định",
            r"nguyên hàm của", r"đồ thị hình bên", r"cho hàm số", r"tỉ lệ thức",
            r"bậc của đa thức", r"nghiệm của đa thức", r"đa thức một biến",
            r"biến cố chắc chắn", r"biến cố không thể", r"khẳng định nào sau đây đúng",
            r"công thức nào", r"tọa độ tâm", r"bán kính", r"vectơ", r"mặt phẳng",
            r"tính chất nào", r"đơn thức", r"hằng đẳng thức"
        ],
        "TH": [
            r"nghiệm của phương trình", r"tổng các nghiệm", r"diện tích hình phẳng",
            r"thể tích khối", r"khoảng cách", r"góc giữa", r"đồng biến trên khoảng",
            r"nghịch biến trên khoảng", r"tam giác có số đo", r"phân tích đa thức",
            r"tích phân", r"xác suất", r"đạo hàm của", r"cắt trục", r"nghiệm nguyên dương"
        ],
        "VD": [
            r"có bao nhiêu giá trị nguyên của tham số", r"tìm tất cả các giá trị của tham số",
            r"để phương trình có \d+ nghiệm", r"giá trị lớn nhất", r"giá trị nhỏ nhất",
            r"tiếp tuyến vuông góc", r"tiếp tuyến song song", r"đồng biến trên tập",
            r"phương trình có nghiệm duy nhất", r"đường thẳng cắt đồ thị tại"
        ],
        "VDC": [
            r"giá trị lớn nhất của biểu thức", r"giá trị nhỏ nhất của biểu thức",
            r"có bao nhiêu bộ số", r"cực trị của biểu thức", r"thể tích lớn nhất",
            r"khoảng cách ngắn nhất", r"bất đẳng thức", r"tham số.*nghiệm phân biệt",
            r"min.*max", r"tối ưu"
        ]
    }

    @classmethod
    def extract_answer_key(cls, full_text: str) -> Dict[int, str]:
        """
        Bóc tách bảng đáp án từ cuối tài liệu nếu có.
        Hỗ trợ:
        - Dạng text: '1.A 2.B 3.C' hoặc '1-A 2-B' hoặc 'Câu 1: A, Câu 2: B'
        - Dạng bảng Markdown: | 1 | 2 | 3 | ... | A | B | C |
        """
        answer_map = {}

        # 1. Tìm phần BẢNG ĐÁP ÁN / ĐÁP ÁN TRẮC NGHIỆM
        ans_section_match = re.search(
            r'(?:BẢNG\s+ĐÁP\s+ÁN|ĐÁP\s+ÁN\s+TRẮC\s+NGHIỆM|ĐÁP\s+ÁN|HƯỚNG\s+DẪN\s+CHẤM)(.*?)(?:----------------|$)',
            full_text,
            flags=re.IGNORECASE | re.DOTALL
        )
        target_text = ans_section_match.group(1) if ans_section_match else full_text

        # Pattern: 1. A hoặc 1 - A hoặc 1: A hoặc Câu 1: A
        pairs = re.findall(
            r'(?:Câu\s+)?(\d+)[\.\s:–\-]+([A-D])(?![a-zA-Z0-9])',
            target_text,
            flags=re.IGNORECASE
        )
        for num_str, letter in pairs:
            q_num = int(num_str)
            if q_num not in answer_map:
                answer_map[q_num] = letter.upper()

        # 2. Pattern bảng markdown: tìm hàng số câu và hàng chữ đáp án
        valid_rows = []
        for line in target_text.split("\n"):
            line = line.strip()
            if line.startswith("|") and "|" in line[1:]:
                # skip separator row |---|---|
                if re.match(r'^\|[\s\-:]+(\|[\s\-:]+)+\|$', line):
                    continue
                cells = [c.strip() for c in line.strip('|').split('|')]
                if cells:
                    valid_rows.append(cells)

        if len(valid_rows) >= 2:
            for r_idx in range(len(valid_rows) - 1):
                row_a = valid_rows[r_idx]
                row_b = valid_rows[r_idx + 1]
                # If first cell is a header label like 'Câu', 'Đáp án', trim it
                if row_a and not re.match(r'^\d+$', row_a[0]):
                    row_a = row_a[1:]
                if row_b and not re.match(r'^[A-D]$', row_b[0], re.I):
                    row_b = row_b[1:]

                if len(row_a) == len(row_b) and len(row_a) >= 2:
                    if all(re.match(r'^\d+$', c) for c in row_a) and all(re.match(r'^[A-D]$', c, re.I) for c in row_b):
                        for c_num, c_ans in zip(row_a, row_b):
                            answer_map[int(c_num)] = c_ans.upper()

        return answer_map

    @classmethod
    def infer_question_tag(cls, question_text: str, question_num: int, total_questions: int = 50) -> str:
        """
        Suy luận Tag mức độ nhận thức: [NB], [TH], [VD], [VDC].
        Ưu tiên từ khóa câu hỏi, sau đó phân bổ theo ma trận đề thi chuẩn Bộ GD&ĐT.
        """
        # Kiểm tra từ khóa từ mức cao đến mức thấp
        q_lower = question_text.lower()
        for tag in ["VDC", "VD", "TH", "NB"]:
            for kw in cls.TAG_KEYWORDS[tag]:
                if re.search(kw, q_lower):
                    return tag

        # Phân bổ theo số thứ tự câu (Chuẩn đề thi 50 câu Bộ GD)
        if total_questions >= 40:
            if question_num <= 15:
                return "NB"
            elif question_num <= 30:
                return "TH"
            elif question_num <= 42:
                return "VD"
            else:
                return "VDC"
        elif total_questions >= 20:
            if question_num <= 8:
                return "NB"
            elif question_num <= 16:
                return "TH"
            elif question_num <= 24:
                return "VD"
            else:
                return "VDC"
        else:
            if question_num <= 4:
                return "NB"
            elif question_num <= 8:
                return "TH"
            elif question_num <= 10:
                return "VD"
            else:
                return "VDC"

    @classmethod
    def format_mcmix(
        cls,
        text: str,
        auto_tag: bool = True,
        underline_correct: bool = True,
        known_answers: Optional[Dict[int, str]] = None
    ) -> str:
        """
        Chuẩn hóa toàn bộ nội dung markdown:
        - Tiền tố: 'Câu X: [TAG]'
        - Gạch chân đáp án đúng: '<u>A.</u>' hoặc '**<u>A.</u>**'
        """
        if not text:
            return ""

        # Trích xuất bảng đáp án nếu chưa có
        answers = known_answers if known_answers is not None else cls.extract_answer_key(text)

        # Đếm tổng số câu hỏi trong tài liệu
        q_nums = [int(m.group(1)) for m in re.finditer(r'(?:^|\n)(?:\*\*)?(?:Câu|Bài)\s+(\d+)', text)]
        total_q = max(q_nums) if q_nums else 50

        lines = text.split("\n")
        new_lines = []
        cur_q_num = None

        q_pattern = re.compile(
            r'^(?:\*\*)?(?:\[([A-Z]{2,3})\]\s*)?(?:Câu|Bài)\s+(\d+)(?:\s*\[([A-Z]{2,3})\])?[\.:\)]?(?:\*\*)?\s*(?:\[([A-Z]{2,3})\])?(?:\s*\(.*?\))?\s*(.*)$',
            re.IGNORECASE
        )

        for line in lines:
            line_stripped = line.strip()

            # 1. Phát hiện dòng mở đầu Câu
            match_q = q_pattern.match(line_stripped)
            if match_q:
                tag_found = match_q.group(1) or match_q.group(3) or match_q.group(4)
                cur_q_num = int(match_q.group(2))
                q_body = match_q.group(5).strip()

                tag = tag_found.upper() if tag_found else None
                if not tag and auto_tag:
                    tag = cls.infer_question_tag(q_body, cur_q_num, total_q)

                tag_str = f"[{tag}] " if tag else ""
                new_lines.append(f"**Câu {cur_q_num}:** {tag_str}{q_body}".strip())
                continue

            # 2. Xử lý các dòng phương án trắc nghiệm A, B, C, D
            # Nếu có đáp án đúng cho cur_q_num trong answers map và underline_correct=True
            if cur_q_num and cur_q_num in answers and underline_correct:
                correct_letter = answers[cur_q_num]

                # Pattern tìm A., B., C., D.
                def mark_correct_opt(m):
                    letter = m.group(1).upper()
                    if letter == correct_letter:
                        return f"**<u>{letter}.</u>** "
                    return f"**{letter}.** "

                # Thay thế các phương án trên dòng
                mod_line = re.sub(
                    r'(?:^|(?<=\s)|(?<=\$\s)|(?<=\\quad\s)|(?<=\t))(?:\*\*)?(?:<u>)?([A-D])[\.:\)](?:</u>)?(?:\*\*)?\s+',
                    mark_correct_opt,
                    line
                )
                new_lines.append(mod_line)
                continue

            # Giữ nguyên dòng khác
            new_lines.append(line)

        return "\n".join(new_lines)
