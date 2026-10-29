import re

class LatexFormatter:
    VN_CHARS = r"àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ"
    VN_REGEX = re.compile(f"[{VN_CHARS}]", re.IGNORECASE)
    UNIT_NAMES = r'm|cm|dm|mm|km|km/h|km/giờ|km/phút|m/giây|m/phút|g|kg|g/cm|inch|giây|giờ|phút|lần|đồng|đồng/kg|mét|ha|s|h'
    UNIT_PATTERN = rf'(?:{UNIT_NAMES}|\(\s*(?:{UNIT_NAMES})\s*\))'

    @classmethod
    def clean_and_normalize(cls, text: str, fix_vietnamese_math: bool = True, fix_decimals: bool = True) -> str:
        r"""
        Cleans and normalizes LaTeX math in text to be 100% compatible with MathType's Toggle TeX (Alt + \).
        """
        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Heal control characters caused by unescaped JSON LaTeX strings:
        # \x09 (tab) -> \text, \times, \theta, \tan, etc.
        text = re.sub(r'\x09ext\b', r'\\text', text)
        text = re.sub(r'\x09imes\b', r'\\times', text)
        text = re.sub(r'\x09heta\b', r'\\theta', text)
        text = re.sub(r'\x09an\b', r'\\tan', text)
        text = re.sub(r'\x09riangle\b', r'\\triangle', text)
        # \x0c (formfeed) -> \frac, \forall
        text = re.sub(r'\x0crac\b', r'\\frac', text)
        text = re.sub(r'\x0call\b', r'\\forall', text)
        # \x08 (backspace) -> \bar, \beta, \begin, \binom, \mathbf
        text = re.sub(r'\x08ar\b', r'\\bar', text)
        text = re.sub(r'\x08eta\b', r'\\beta', text)
        text = re.sub(r'\x08egin\b', r'\\begin', text)
        text = re.sub(r'\x08inom\b', r'\\binom', text)
        text = re.sub(r'\x08mathbf\b', r'\\mathbf', text)
        # \x0d (carriage return) -> \right, \rho, etc.
        text = re.sub(r'\x0dight\b', r'\\right', text)
        text = re.sub(r'\x0dho\b', r'\\rho', text)

        # Clean accidental ext[A-D] artifacts
        text = re.sub(r'(?<![a-zA-Z\\])ext\s*([A-D][\.:\)])', r'\1', text)

        # Clean accidental \ext or ext attached to units (extm, \extm, ext m) outside or inside math
        text = re.sub(r'\\ext\{([^}]+)\}', r'\\text{\1}', text)
        text = re.sub(rf'\\ext\s*({cls.UNIT_PATTERN})\b', r'\\text{ \1}', text)
        text = re.sub(r'\\ext\b', r'\\text', text)
        text = re.sub(r'(?<![a-zA-Z\\])ext\s*(Hình|Bài|Câu|Cách|Ví dụ)\b', r'\1', text)
        text = re.sub(r'(?<![a-zA-Z\\])ext\{([^}]+)\}', r'\\text{\1}', text)
        text = re.sub(rf'(?<![a-zA-Z\\])ext\s*({cls.UNIT_PATTERN})\b', r'\\text{ \1}', text)

        # Replace HTML <br> tags outside of tables, but preserve <br> inside tables
        lines = text.split("\n")
        preserved_lines = []
        for l in lines:
            stripped = l.strip()
            if stripped.startswith("|") and "|" in stripped[1:]:
                # Keep <br> inside tables as cell line breaks
                preserved_lines.append(l)
            else:
                preserved_lines.append(re.sub(r'<br\s*/?>', '\n', l, flags=re.IGNORECASE))
        text = "\n".join(preserved_lines)

        # Auto-heal pages where Gemini hallucinated raw .tex mode with \text{Câu}, \text{Tam giác} outside of $...$
        text = cls._heal_broken_latex_mode(text)

        # Normalize escaped delimiters \( ... \) -> $ ... $, \[ ... \] -> $$ ... $$
        text = re.sub(r'\\\((.*?)\\\)', r'$\1$', text, flags=re.DOTALL)
        text = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', text, flags=re.DOTALL)

        # Convert isolated LaTeX spacing tags into clean Word tabs
        text = re.sub(r'\$\s*\\(q?quad|enspace)\s*\$', '\t\t', text)
        text = re.sub(r'(?<!\$)\\(q?quad|enspace)(?!\$)', '\t\t', text)

        # Clean LaTeX layout artefacts that sometimes leak into markdown
        text = re.sub(r'\\hfill\b', '\t\t', text)
        text = re.sub(r'\\(Large|large|Huge|huge|small|footnotesize)\b\s*', '', text)
        text = re.sub(r'\\textbf\{([^}]+)\}', r'**\1**', text)

        # Fix geometric points accidentally wrapped in \text{} e.g. \text{A}, \text{BC}, \text{ABC}
        text = re.sub(r'\\text\{([A-Z]{1,4})\}', r'\1', text)

        # Fix geometric coordinate systems & axes in plain Vietnamese text
        text = re.sub(r'\b0([xyz]{2,3})\b', r'O\1', text)
        text = re.sub(r'\(0([xyz]{2,3})\)', r'(O\1)', text)
        text = re.sub(r'\btrục\s+0([xyz])\b', r'trục O\1', text, flags=re.IGNORECASE)
        text = re.sub(r'\bhệ\s+trục\s+0xyz\b', r'hệ trục Oxyz', text, flags=re.IGNORECASE)
        text = re.sub(r'\bmặt\s+phẳng\s+\(0([xyz]{2})\)', r'mặt phẳng (O\1)', text, flags=re.IGNORECASE)
        text = re.sub(r'(\d+)\s*°(?!\w)', r'$\1^\\circ$', text)

        # Process block math ($$ ... $$)
        def replace_block_math(match):
            formula = match.group(1).strip()
            if not formula:
                return ""
            # If formula accidentally contains entire Vietnamese headings or questions, unwrap to text
            if re.search(r'\b(Câu|Bài|Khẳng định|Phần|Trắc nghiệm)\b', formula):
                unwrapped = re.sub(r'\\text\{([^}]+)\}', r'\1', formula)
                unwrapped = re.sub(r'\\mathbf\{([^}]+)\}', r'**\1**', unwrapped)
                return unwrapped
            if fix_vietnamese_math:
                formula = cls._fix_vietnamese_in_formula(formula)
            if fix_decimals:
                formula = cls._fix_decimal_commas(formula)
            formula = cls._standardize_math_symbols(formula, is_block=True)
            return f"$${formula}$$"

        # Process inline math ($ ... $) - Strictly single line!
        def replace_inline_math(match):
            formula = match.group(1).strip()
            if not formula:
                return ""
            # If formula accidentally contains entire Vietnamese sentences/questions, unwrap
            if re.search(r'\b(Câu|Bài|Khẳng định|Chọn|Tìm|Tính|Chứng minh|Hãy|Biết rằng)\b', formula):
                unwrapped = re.sub(r'\\text\{([^}]+)\}', r'\1', formula)
                return unwrapped
            if fix_vietnamese_math:
                formula = cls._fix_vietnamese_in_formula(formula)
            if fix_decimals:
                formula = cls._fix_decimal_commas(formula)
            formula = cls._standardize_math_symbols(formula, is_block=False)
            return f"${formula}$"

        text = re.sub(r'\$\$([^\$]+?)\$\$', replace_block_math, text, flags=re.DOTALL)
        text = re.sub(r'(?<!\$)\$(?!\$)([^\$\n]+?)(?<!\$)\$(?!\$)', replace_inline_math, text)

        # Clean markdown list markers like *a1)* or *b2)* -> **a1)**
        text = re.sub(r'\*([a-z]\d?\))\*', r'**\1**', text)

        return text

    @classmethod
    def _fix_vietnamese_in_formula(cls, formula: str) -> str:
        r"""
        Wraps true Vietnamese text inside formulas with \text{...}, while protecting geometry vertices and math variables.
        """
        # First fix subscripts like _{tam giác} -> _{\text{tam giác}}
        def fix_sub_super(m):
            prefix = m.group(1)
            content = m.group(2).strip()
            if not content.startswith(r'\text{') and not content.startswith(r'\mathrm{'):
                if cls.VN_REGEX.search(content) or " " in content:
                    return f"{prefix}{{\\text{{{content}}}}}"
            return m.group(0)

        formula = re.sub(r'([_^])\{([^}]+)\}', fix_sub_super, formula)

        # Protect geometric vertices like \text{A}, \text{BC}
        formula = re.sub(r'\\text\{([A-Z]{1,4})\}', r'\1', formula)

        # Split by existing \text{...} or \mathrm{...}
        parts = re.split(r'(\\text\{.*?\}|\\mathrm\{.*?\})', formula)
        new_parts = []
        for part in parts:
            if part.startswith(r'\text{') or part.startswith(r'\mathrm{'):
                new_parts.append(part)
            else:
                # Wrap ONLY words containing actual Vietnamese accented vowels
                def wrap_vn(m):
                    word = m.group(0)
                    if cls.VN_REGEX.search(word):
                        return f"\\text{{{word}}}"
                    return word
                part = re.sub(r'[a-zA-Z' + cls.VN_CHARS + r']+', wrap_vn, part)
                new_parts.append(part)

        return "".join(new_parts)

    @classmethod
    def _fix_decimal_commas(cls, formula: str) -> str:
        return re.sub(r'(\d+),(\d+)', r'\1{,}\2', formula)

    @classmethod
    def _standardize_math_symbols(cls, formula: str, is_block: bool = False) -> str:
        r"""
        Deep Math Sanitizer:
        - Chuẩn hóa gốc tọa độ O vs số 0 (0xyz -> Oxyz, 0xy -> Oxy, trục 0x -> trục Ox)
        - Chuẩn hóa ký hiệu góc (\widehat{ABC}) và độ (60^\circ)
        - Chuẩn hóa hệ phương trình & hệ ngoặc vuông tuyển nghiệm
        - Giữ nguyên \sim cho hình học đồng dạng, chuẩn hóa \approx
        - Chuẩn hóa tam giác (\Delta), vector (\overrightarrow{AB}) và phân số (\dfrac trong block)
        """
        # 1. Gốc tọa độ O vs số 0
        formula = re.sub(r'\b0xyz\b', 'Oxyz', formula)
        formula = re.sub(r'\b0xy\b', 'Oxy', formula)
        formula = re.sub(r'\b0yz\b', 'Oyz', formula)
        formula = re.sub(r'\b0xz\b', 'Oxz', formula)
        formula = re.sub(r'\b0([xyz])\b', r'O\1', formula)
        formula = re.sub(r'\b0\s*\(\s*0\s*;\s*0', 'O(0; 0', formula)
        formula = re.sub(r'\\Delta\s*0([A-Z])', r'\\Delta O\1', formula)

        # 2. Góc và độ
        formula = re.sub(r'(\d+)\s*(?:\^0|\^[oO]|°)(?!\w)', r'\1^\\circ', formula)
        formula = re.sub(r'\\(angle|measuredangle)\s*\{?([A-Za-z0-9_\']{1,8})\}?', r'\\widehat{\2}', formula)
        formula = re.sub(r'\\hat\{([A-Za-z0-9_\']{1,8})\}', r'\\widehat{\1}', formula)
        formula = re.sub(r'\\widehat\s+([A-Za-z0-9_\']{1,8})', r'\\widehat{\1}', formula)

        # 3. Hệ phương trình & hệ tuyển
        formula = re.sub(r'\\left\\\{\s*\\begin\{array\}\{[lcr]\}', r'\\begin{cases}', formula)
        formula = re.sub(r'\\end\{array\}\s*\\right\.?', r'\\end{cases}', formula)
        formula = re.sub(r'\\left\[\s*\\begin\{cases\}', r'\\left[\\begin{array}{l}', formula)
        formula = re.sub(r'\\end\{cases\}\s*\\right\.?', r'\\end{array}\\right.', formula)

        # 4. Xấp xỉ, suy ra, tương đương, bất đẳng thức (giữ nguyên \sim cho tam giác đồng dạng)
        formula = re.sub(r'(?<=\s)~\s*(?=[0-9\\+-])', r'\\approx ', formula)
        formula = re.sub(r'(?:<=>|\\iff\b)', r'\\Leftrightarrow', formula)
        formula = re.sub(r'(?:=>|\\implies\b)', r'\\Rightarrow', formula)
        formula = re.sub(r'<=', r'\\le', formula)
        formula = re.sub(r'>=', r'\\ge', formula)

        # 5. Tam giác, vector và phân số
        formula = re.sub(r'\\(triangle|bigtriangleup)\b', r'\\Delta', formula)
        formula = re.sub(r'\\vec\{([A-Za-z]{2,})\}', r'\\overrightarrow{\1}', formula)
        if is_block:
            formula = re.sub(r'\\frac(?=\{)', r'\\dfrac', formula)

        # 6. Chuẩn hóa đơn vị đo lường và loại bỏ triệt để ext dính vào đơn vị (extm -> \text{ m})
        formula = re.sub(r'\\ext\{([^}]+)\}', r'\\text{\1}', formula)
        formula = re.sub(rf'\\ext\s*({cls.UNIT_PATTERN})\b', r'\\text{ \1}', formula)
        formula = re.sub(r'\\ext\b', r'\\text', formula)
        formula = re.sub(r'(?<![a-zA-Z\\])ext\{([^}]+)\}', r'\\text{\1}', formula)
        formula = re.sub(rf'(?<![a-zA-Z\\])ext\s*({cls.UNIT_PATTERN})\b', r'\\text{ \1}', formula)
        # Đảm bảo có khoảng trắng chuẩn trước đơn vị đo trong công thức: 2{,}4\text{m} -> 2{,}4\text{ m}
        formula = re.sub(rf'(\d+(?:\{{,}}\d+)?)\s*\\text\{{\s*({cls.UNIT_PATTERN})\s*\}}', r'\1\\text{ \2}', formula)

        return formula

    @classmethod
    def _heal_broken_latex_mode(cls, text: str) -> str:
        """
        Fixes pages where Gemini hallucinated into full .tex source mode:
        1. Strips \\text{...} from regular Vietnamese words outside of $...$ (e.g. \\text{Câu} 1, \\text{Tam giác}).
        2. Auto-wraps orphaned formulas (\\frac, \\sqrt, \\sin, \\cos) in $...$.
        3. Cleans up empty scan box artefacts (□, \\Box).
        """
        # Split text into math parts ($...$ or $$...$$) and non-math parts (inline math strictly non-newline)
        tokens = re.split(r'(\$\$[^\$]+?\$\$|\$[^\$\n]+?\$)', text)
        new_tokens = []
        for token in tokens:
            if token.startswith("$"):
                new_tokens.append(token)
            else:
                # 1. Strip \\text{...} from outside text
                cleaned = re.sub(r'\\text\{([^}]+)\}', r'\1', token)
                # 2. Clean scan font artefacts like □ or \\Box
                cleaned = cleaned.replace("□", "").replace(r"\Box", "")

                # 3. Detect and auto-wrap orphaned formulas (e.g. A. \\frac{\\sqrt{55}}{2})
                lines = cleaned.split("\n")
                fixed_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    # Choice lines: A. \\frac{...} or A. P = ...
                    opt_match = re.match(r'^([A-D]\.\s*)(.*\\(frac|dfrac|sqrt|sin|cos|tan|cot|pi|vec|overrightarrow).*)$', line_stripped)
                    if opt_match:
                        prefix = opt_match.group(1)
                        math_body = opt_match.group(2).rstrip('.')
                        fixed_lines.append(f"{prefix}${math_body}$.")
                        continue

                    # Expressions after colon: ta có: \\frac{...}
                    colon_match = re.search(r'(:\s*)((\\frac|\\dfrac|\\sqrt|\\sin|\\cos|P\s*=).*)$', line_stripped)
                    if colon_match:
                        prefix = line_stripped[:colon_match.start() + len(colon_match.group(1))]
                        math_body = colon_match.group(2).rstrip('.')
                        fixed_lines.append(f"{prefix}${math_body}$.")
                        continue

                    # Standalone equation with math functions: e.g. P = \sin 20^\circ ... là
                    func_match = re.search(r'([A-Za-z]\s*=\s*.*\\(sin|cos|tan|cot|sqrt|dfrac|frac).*)', line_stripped)
                    if func_match:
                        prefix = line_stripped[:func_match.start()]
                        math_body = func_match.group(1).rstrip('.')
                        tail_vn = re.search(r'(\s+(là|bằng)\b.*)$', math_body, flags=re.IGNORECASE)
                        if tail_vn:
                            tail = tail_vn.group(1)
                            math_body = math_body[:tail_vn.start()].strip()
                            fixed_lines.append(f"{prefix}${math_body}${tail}")
                        else:
                            fixed_lines.append(f"{prefix}${math_body}$.")
                        continue

                    fixed_lines.append(line)
                new_tokens.append("\n".join(fixed_lines))

        return "".join(new_tokens)


