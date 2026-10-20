import os
import re
import shutil
from typing import Dict, List, Optional, Tuple

QUESTION_START_RE = re.compile(
    r'^(?:\[(?:NB|TH|VD|VDC)\]\s*)?(?:\*\*)?(?:(?:Câu|Bài|Ví dụ|Khẳng định|Mệnh đề)\s+\d+|[0-9]{1,3}[\.\:])[\.\:\s\)]',
    re.IGNORECASE
)
OPTION_START_RE = re.compile(r'^(?:\*\*)?(?:<u>)?(?:\*\*)?[A-D][\.\:\)]', re.IGNORECASE)
SOLUTION_START_RE = re.compile(r'^(?:\*\*)?(?:Lời giải|Hướng dẫn giải|Giải|HDG|Bài giải)[\:\.]', re.IGNORECASE)

class LatexExporter:
    """
    Xuất tài liệu sang file LaTeX (.tex) hoàn chỉnh, tương thích 100% với:
    - TeXmaker
    - TeXStudio
    - Overleaf
    - MiKTeX / TeX Live
    """

    PREAMBLE_TEMPLATE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[vietnamese]{babel}
\usepackage{amsmath,amssymb,amsfonts,amsthm}
\usepackage{geometry}
\geometry{a4paper, left=20mm, right=20mm, top=20mm, bottom=20mm}
\usepackage{graphicx}
\usepackage{multicol}
\usepackage{tasks}
\usepackage{tikz}
\usepackage{enumitem}
\usepackage{fancyhdr}
\usepackage{tabularx}
\usepackage{booktabs}
\usepackage{ulem}
\usepackage[export]{adjustbox}

% Cấu hình gói tasks cho trắc nghiệm 4 cột / 2 cột
\settasks{
    label=\textbf{\Alph*.},
    label-format={\bfseries},
    label-width=18pt,
    item-indent=22pt,
    column-sep=10pt,
    after-item-skip=3pt
}

\pagestyle{fancy}
\fancyhf{}
\rhead{}
\lhead{\textbf{__HEADER_TITLE__}}
\rfoot{Trang \thepage}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0.4pt}

\begin{document}

\begin{center}
    {\LARGE \textbf{__MAIN_TITLE__}}\\[6pt]
    \rule{0.6\textwidth}{0.8pt}
\end{center}
\vspace{1em}

__CONTENT__

\end{document}
"""

    @classmethod
    def export_to_tex(
        cls,
        base_name: str,
        all_markdown_pages: List[str],
        per_page_image_maps: Dict[int, Dict[str, str]],
        output_dir: str = "output",
        title: Optional[str] = None
    ) -> str:
        """
        Xuất danh sách các trang markdown thành file .tex duy nhất kèm sao chép ảnh vào thư mục figures/
        """
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        tex_filename = f"{base_name}_Converted.tex"
        tex_path = os.path.join(output_dir, tex_filename)

        # Thư mục figures cạnh file .tex
        figures_dir = os.path.join(output_dir, "figures")
        os.makedirs(figures_dir, exist_ok=True)

        # Map lưu đường dẫn relative sang figures/
        rel_image_map = {}
        for p_num, img_map in per_page_image_maps.items():
            for fig_id, src_path in img_map.items():
                if os.path.exists(src_path):
                    fig_ext = os.path.splitext(src_path)[1] or ".png"
                    dest_filename = f"page_{p_num:04d}_{fig_id}{fig_ext}"
                    dest_path = os.path.join(figures_dir, dest_filename)
                    try:
                        shutil.copy2(src_path, dest_path)
                    except Exception:
                        pass
                    # TeX sử dụng forward slash '/' cho đường dẫn file
                    rel_image_map[fig_id] = f"figures/{dest_filename}"

        # Chuyển đổi từng trang Markdown sang LaTeX
        tex_pages = []
        for p_idx, md_content in enumerate(all_markdown_pages):
            tex_page = cls._convert_page_markdown_to_tex(md_content, rel_image_map)
            tex_pages.append(tex_page)

        full_body = "\n\n\\newpage\n\n".join(tex_pages)

        main_title = title or f"TÀI LIỆU TOÁN HỌC: {base_name.upper().replace('_', ' ')}"
        header_title = base_name.replace("_", " ")

        tex_content = cls.PREAMBLE_TEMPLATE.replace("__HEADER_TITLE__", header_title)
        tex_content = tex_content.replace("__MAIN_TITLE__", main_title)
        tex_content = tex_content.replace("__CONTENT__", full_body)

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex_content)

        return tex_path

    @classmethod
    def _convert_page_markdown_to_tex(cls, text: str, rel_image_map: Dict[str, str]) -> str:
        """
        Chuyển đổi nội dung một trang markdown sang LaTeX tương thích TeXmaker / Overleaf.
        """
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out_lines = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # 1. Bảng Markdown
            if line.startswith("|") and "|" in line[1:]:
                table_lines = [line]
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line.startswith("|"):
                        table_lines.append(next_line)
                        i += 1
                    else:
                        break
                tex_table = cls._convert_table_to_tex(table_lines, rel_image_map)
                out_lines.append(tex_table)
                continue

            # Smart Fluid Layout: Question + Figure side-by-side using minipages
            if QUESTION_START_RE.match(line):
                side_tex, next_k = cls._try_render_side_by_side_tex(lines, i, rel_image_map)
                if side_tex is not None:
                    out_lines.append(side_tex)
                    i = next_k
                    continue

            # 2. Hình ảnh độc lập [HINH_X]
            fig_match = re.match(r'^\[(HINH_\w+)\]$', line)
            if fig_match:
                fig_id = fig_match.group(1)
                img_rel = rel_image_map.get(fig_id)
                if img_rel:
                    out_lines.append(
                        f"\\begin{{center}}\n"
                        f"    \\includegraphics[max width=0.65\\textwidth]{{{img_rel}}}\n"
                        f"\\end{{center}}"
                    )
                i += 1
                continue

            # 3. Tiêu đề Markdown
            if line.startswith("# "):
                t = cls._format_inline_text(line[2:].strip())
                out_lines.append(f"\\begin{{center}}\n    {{\\Large \\textbf{{{t}}}}}\n\\end{{center}}\n")
                i += 1
                continue
            elif line.startswith("## ") or line.startswith("### "):
                p_len = 3 if line.startswith("## ") else 4
                t = cls._format_inline_text(line[p_len:].strip())
                out_lines.append(f"\\subsubsection*{{{t}}}")
                i += 1
                continue

            # 4. Trắc nghiệm A, B, C, D -> tasks environment
            mc_result = cls._try_parse_mc_options(lines, i)
            if mc_result is not None:
                options, next_i = mc_result
                tasks_block = cls._render_mc_tasks(options, rel_image_map)
                out_lines.append(tasks_block)
                i = next_i
                continue

            # 5. Dòng câu hỏi hoặc đoạn văn thông thường
            fmt_line = cls._format_inline_text(line)
            # Thay thế [HINH_X] nằm giữa dòng
            for f_id, f_rel in rel_image_map.items():
                if f"[{f_id}]" in fmt_line:
                    img_code = f"\n\\begin{{center}}\\includegraphics[max width=0.55\\textwidth]{{{f_rel}}}\\end{{center}}\n"
                    fmt_line = fmt_line.replace(f"[{f_id}]", img_code)

            if re.match(r'^(?:\\textbf\{)?(?:Câu|Bài|Ví dụ)\s+\d+', fmt_line):
                out_lines.append(f"\\noindent {fmt_line}\\\\[2pt]")
            else:
                out_lines.append(f"{fmt_line}\n")

            i += 1

        return "\n".join(out_lines)

    @classmethod
    def _try_render_side_by_side_tex(
        cls, lines: List[str], start_idx: int, rel_image_map: Dict[str, str]
    ) -> Tuple[Optional[str], int]:
        """
        Đưa câu hỏi và hình vẽ liên kết hiển thị song song (Side-by-Side) bằng minipages trong LaTeX.
        """
        prompt_lines = []
        k = start_idx
        max_scan = min(len(lines), start_idx + 10)
        fig_found = False

        while k < max_scan:
            line_k = lines[k].strip()
            if not line_k:
                if fig_found:
                    break
                k += 1
                continue

            if OPTION_START_RE.match(line_k) or cls._try_parse_mc_options(lines, k) is not None:
                break
            if k > start_idx and QUESTION_START_RE.match(line_k):
                break
            if SOLUTION_START_RE.match(line_k):
                break
            if line_k.startswith("|") or line_k.startswith("#"):
                break

            if re.search(r'\[(HINH_\w+)\]', line_k):
                fig_found = True

            prompt_lines.append(line_k)
            k += 1

        if not prompt_lines:
            return None, start_idx

        combined_text = " ".join(prompt_lines)
        fig_matches = re.findall(r'\[(HINH_\w+)\]', combined_text)
        if not fig_matches or len(set(fig_matches)) != 1:
            return None, start_idx

        fig_id = fig_matches[0]
        img_rel = rel_image_map.get(fig_id)
        if not img_rel:
            return None, start_idx

        # Clean prompt lines
        clean_lines = []
        for pl in prompt_lines:
            cl = re.sub(r'\[HINH_\w+\]', '', pl).strip()
            cl = re.sub(r'\s{2,}', ' ', cl)
            if cl:
                clean_lines.append(cls._format_inline_text(cl))

        if not clean_lines:
            return None, start_idx

        left_content = "\\par\n    ".join(clean_lines)

        tex_code = (
            f"\\noindent\n"
            f"\\begin{{minipage}}[t]{{0.65\\textwidth}}\n"
            f"    {left_content}\n"
            f"\\end{{minipage}}\\hfill\n"
            f"\\begin{{minipage}}[t]{{0.32\\textwidth}}\n"
            f"    \\centering\n"
            f"    \\includegraphics[max width=\\textwidth]{{{img_rel}}}\n"
            f"\\end{{minipage}}\\par\\vspace{{4pt}}"
        )
        return tex_code, k

    @classmethod
    def _try_parse_mc_options(cls, lines: List[str], start_idx: int) -> Optional[Tuple[List[str], int]]:
        """
        Nhận diện khối 4 phương án trắc nghiệm A, B, C, D.
        """
        line = lines[start_idx].strip()
        if not line:
            return None

        # Khởi đầu phương án A
        if not re.match(r'^(?:[-*•]\s+)?(?:\*\*|\*)?(?:<u>|\\underline\{)?A[\.:\)](?:</u>|\})?(?:\*\*|\*)?\s+', line):
            return None

        gathered = []
        indices = []
        stop_re = re.compile(r'^(?:#|\||\[HINH_\w+\]|(?:\*\*)?(?:Câu|Bài|Phần|PHẦN|ĐỀ)\s+\d+)', re.I)
        opt_re = re.compile(r'(?:^|(?<=\s)|(?<=\$\s)|(?<=\\quad\s)|(?<=\t))(?:\*\*|\*)?(?:<u>|\\underline\{)?([A-D])[\.:\)](?:</u>|\})?(?:\*\*|\*)?\s+')

        j = start_idx
        while j < len(lines):
            cur = lines[j].strip()
            if not cur:
                j += 1
                continue
            if j > start_idx and stop_re.search(cur):
                break
            gathered.append(cur)
            indices.append(j)

            comb = "\n".join(gathered)
            matches = list(opt_re.finditer(comb))
            if 'D' in [m.group(1) for m in matches]:
                break
            if len(gathered) > 8:
                break
            j += 1

        if not gathered:
            return None

        full_text = "\n".join(gathered)
        matches = list(opt_re.finditer(full_text))
        letters = [m.group(1) for m in matches]
        if letters != ['A', 'B', 'C', 'D']:
            return None

        options = []
        for k in range(4):
            st = matches[k].start()
            en = matches[k+1].start() if k < 3 else len(full_text)
            opt_str = full_text[st:en].strip()
            opt_str = re.sub(r'(\$\\quad\$|\\quad|\\qquad|\t|\s)+$', '', opt_str).strip()
            options.append(opt_str)

        return options, indices[-1] + 1

    @classmethod
    def _render_mc_tasks(cls, options: List[str], rel_image_map: Dict[str, str]) -> str:
        """
        Xuất 4 phương án sang môi trường \\begin{tasks}(cols) ... \\end{tasks}.
        Hỗ trợ gạch chân đáp án đúng: \\underline{\\textbf{A.}}
        """
        # Xác định số cột (4, 2, hoặc 1)
        plain_lens = []
        clean_opts = []
        for opt in options:
            # Phát hiện nếu đáp án có gạch chân
            is_underlined = bool(re.search(r'<u>|[\\_]underline\{', opt))
            # Bóc tách nội dung sau nhãn
            body_match = re.search(r'^[^\s]+\s+(.*)$', opt, re.DOTALL)
            content = body_match.group(1).strip() if body_match else opt

            clean_opts.append((is_underlined, content))
            # Ước lượng độ dài
            plain = re.sub(r'\$[^\$]+\$', 'MathExpr', content)
            plain = re.sub(r'\\[a-zA-Z]+', '', plain)
            plain_lens.append(len(plain))

        max_len = max(plain_lens)
        total_len = sum(plain_lens)

        if max_len <= 16 and total_len <= 60:
            cols = 4
        elif max_len <= 40 and total_len <= 150:
            cols = 2
        else:
            cols = 1

        out = [f"\\begin{{tasks}}({cols})"]
        letters = ['A', 'B', 'C', 'D']
        for idx, (is_underlined, content) in enumerate(clean_opts):
            let = letters[idx]
            fmt_content = cls._format_inline_text(content)

            # Chèn hình minh họa trong phương án nếu có
            for f_id, f_rel in rel_image_map.items():
                if f"[{f_id}]" in fmt_content:
                    img_code = f" \\includegraphics[max width=0.25\\textwidth]{{{f_rel}}} "
                    fmt_content = fmt_content.replace(f"[{f_id}]", img_code)

            if is_underlined:
                out.append(f"    \\task \\underline{{\\textbf{{{let}.}}}} {fmt_content}")
            else:
                out.append(f"    \\task \\textbf{{{let}.}} {fmt_content}")

        out.append("\\end{tasks}")
        return "\n".join(out)

    @classmethod
    def _convert_table_to_tex(cls, table_lines: List[str], rel_image_map: Dict[str, str]) -> str:
        """
        Chuyển đổi bảng Markdown sang môi trường tabular LaTeX chuẩn.
        """
        rows = []
        for line in table_lines:
            if re.match(r'^\|[\s\-:]+(\|[\s\-:]+)+\|$', line):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            rows.append(cells)

        if not rows:
            return ""

        col_count = max(len(r) for r in rows)
        col_spec = "c" * col_count

        out = [
            "\\begin{center}",
            f"\\begin{{tabular}}{{|{ '|'.join(['c'] * col_count) }|}}",
            "\\hline"
        ]

        for row_idx, r in enumerate(rows):
            # Pad short rows
            while len(r) < col_count:
                r.append("")
            cell_texts = []
            for c in r:
                # Xử lý <br> thành dòng trong bảng
                c_clean = c.replace("<br>", " \\newline ")
                c_clean = cls._format_inline_text(c_clean)
                for f_id, f_rel in rel_image_map.items():
                    if f"[{f_id}]" in c_clean:
                        c_clean = c_clean.replace(f"[{f_id}]", f"\\includegraphics[width=2.5cm]{{{f_rel}}}")
                if row_idx == 0:
                    c_clean = f"\\textbf{{{c_clean}}}"
                cell_texts.append(c_clean)

            out.append(" & ".join(cell_texts) + " \\\\ \\hline")

        out.append("\\end{tabular}")
        out.append("\\end{center}")
        return "\n".join(out)

    @classmethod
    def _format_inline_text(cls, text: str) -> str:
        """
        Chuẩn hóa các thẻ Markdown (**in đậm**, *nghiêng*, <u>gạch chân</u>) sang lệnh LaTeX.
        Bảo toàn các công thức Toán $...$ và $$...$$.
        """
        if not text:
            return ""

        # Tách công thức toán để tránh escape nhầm ký hiệu toán học
        tokens = re.split(r'(\$\$[^\$]+?\$\$|\$[^\$\n]+?\$)', text)
        new_tokens = []

        for token in tokens:
            if token.startswith("$"):
                # Công thức toán giữ nguyên vẹn
                new_tokens.append(token)
            else:
                s = token
                # Chuyển đổi bold **text** -> \textbf{text}
                s = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', s)
                # Chuyển đổi italic *text* -> \textit{text}
                s = re.sub(r'\*([^*]+)\*', r'\\textit{\1}', s)
                # Chuyển đổi underline <u>text</u> -> \underline{text}
                s = re.sub(r'<u>(.*?)</u>', r'\\underline{\1}', s)
                # Escape các ký tự đặc biệt ngoài toán: % -> \%, & -> \& (ngoài bảng)
                # Không escape dấu gạch chéo ngược \ hoặc { }
                s = re.sub(r'(?<!\\)%', r'\\%', s)
                new_tokens.append(s)

        return "".join(new_tokens)
