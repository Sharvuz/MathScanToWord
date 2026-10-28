import os
import re
from typing import List, Dict, Any, Optional, Tuple
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from core.omml_converter import OMMLConverter
from core.latex_formatter import LatexFormatter

QUESTION_START_RE = re.compile(
    r'^(?:\[(?:NB|TH|VD|VDC)\]\s*)?(?:\*\*)?(?:(?:Câu|Bài|Ví dụ|Khẳng định|Mệnh đề)\s+\d+|[0-9]{1,3}[\.\:])[\.\:\s\)]',
    re.IGNORECASE
)
OPTION_START_RE = re.compile(r'^(?:\*\*)?(?:<u>)?(?:\*\*)?[A-D][\.\:\)]', re.IGNORECASE)
SOLUTION_START_RE = re.compile(r'^(?:\*\*)?(?:Lời giải|Hướng dẫn giải|Giải|HDG|Bài giải)[\:\.]', re.IGNORECASE)

class WordBuilder:
    def __init__(
        self,
        font_name: str = "Times New Roman",
        font_size_pt: float = 13.0,
        convert_to_omml: bool = True,
        toggle_tex_mode: bool = False,
        format_multiple_choice: bool = True,
        smart_layout: bool = True
    ):
        self.doc = docx.Document()
        self.font_name = font_name
        self.font_size_pt = font_size_pt
        self.toggle_tex_mode = toggle_tex_mode
        self.convert_to_omml = convert_to_omml and (not toggle_tex_mode)
        self.format_multiple_choice = format_multiple_choice
        self.smart_layout = smart_layout
        self._setup_page_margins()
        self._setup_default_styles()

    def _setup_page_margins(self):
        # 2cm margins (~0.79 inches)
        for section in self.doc.sections:
            section.top_margin = Inches(0.79)
            section.bottom_margin = Inches(0.79)
            section.left_margin = Inches(0.79)
            section.right_margin = Inches(0.79)

    def _setup_default_styles(self):
        style = self.doc.styles['Normal']
        font = style.font
        font.name = self.font_name
        font.size = Pt(self.font_size_pt)
        font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.line_spacing = 1.15
        style.paragraph_format.space_after = Pt(3)

    def add_header_title(self, title: str):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(title)
        run.bold = True
        run.font.name = self.font_name
        run.font.size = Pt(self.font_size_pt + 3)
        run.font.color.rgb = RGBColor(0, 32, 96)

    def add_page_content(
        self,
        page_num: int,
        markdown_text: str,
        image_map: Dict[str, str],
        selected_image_ids: Optional[List[str]] = None
    ):
        if selected_image_ids is None:
            selected_image_ids = list(image_map.keys())

        used_image_ids = set()

        # Normalize line breaks
        lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        
        # Parse page lines into blocks (Tables vs Paragraphs vs Images)
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Check if line starts a markdown table
            if line.startswith("|") and "|" in line[1:]:
                table_raw_rows = []
                cur_row = line
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if not next_line:
                        # Empty line can mean table ended or gap
                        if cur_row.endswith("|"):
                            table_raw_rows.append(cur_row)
                            cur_row = ""
                            i += 1
                            break
                        else:
                            i += 1
                            continue
                    
                    if next_line.startswith("|"):
                        if cur_row.endswith("|"):
                            table_raw_rows.append(cur_row)
                            cur_row = next_line
                        else:
                            cur_row += " " + next_line
                    else:
                        if cur_row:
                            cur_row += " " + next_line
                        else:
                            break
                    i += 1

                if cur_row:
                    table_raw_rows.append(cur_row)

                if table_raw_rows:
                    self._render_markdown_table(table_raw_rows, image_map, selected_image_ids)
                continue

            # Smart Fluid Layout: Render Question Prompt + Figure side-by-side in a 2-column borderless table
            if self.smart_layout and self._is_question_start(line):
                side_next = self._try_render_side_by_side_question_figure(
                    lines, i, image_map, selected_image_ids, used_image_ids
                )
                if side_next is not None:
                    i = side_next
                    continue

            # Check for image placeholder [HINH_X]
            fig_match = re.search(r'\[(HINH_\w+)\]', line)
            if fig_match:
                fig_id = fig_match.group(1)
                used_image_ids.add(fig_id)
                before_text = line[:fig_match.start()].strip()
                if before_text:
                    self._add_formatted_paragraph(before_text)

                if fig_id in image_map and fig_id in selected_image_ids:
                    img_path = image_map[fig_id]
                    if os.path.exists(img_path):
                        self._insert_image(img_path)

                after_text = line[fig_match.end():].strip()
                if after_text:
                    self._add_formatted_paragraph(after_text)

                i += 1
                continue

            # Check headings
            if line.startswith("# "):
                p = self.doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(4)
                self._format_text_with_math_and_bold(p, line[2:].strip(), is_heading=True, heading_level=1)
            elif line.startswith("## ") or line.startswith("### "):
                p = self.doc.add_paragraph()
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(3)
                prefix_len = 3 if line.startswith("## ") else 4
                self._format_text_with_math_and_bold(p, line[prefix_len:].strip(), is_heading=True, heading_level=2)
            else:
                # Check for multiple-choice options (A, B, C, D)
                if self.format_multiple_choice:
                    mc_result = self._try_parse_multiple_choice(lines, i)
                    if mc_result is not None:
                        options, next_i = mc_result
                        self._render_multiple_choice_table(options, image_map, selected_image_ids, used_image_ids)
                        i = next_i
                        continue

                p = self.doc.add_paragraph()
                if re.match(r'^(?:\*\*)?(?:Câu|Bài|Khẳng định|Ví dụ)\s+\d+', line):
                    p.paragraph_format.space_before = Pt(4)
                    p.paragraph_format.space_after = Pt(2)
                else:
                    p.paragraph_format.space_before = Pt(1)
                    p.paragraph_format.space_after = Pt(2)
                self._format_text_with_math_and_bold(p, line)

            i += 1

        # Embed any remaining selected figures for this page that had no placeholder in text (e.g. manually added figures)
        for fig_id in selected_image_ids:
            if fig_id in image_map and fig_id not in used_image_ids:
                img_path = image_map[fig_id]
                if os.path.exists(img_path):
                    self._insert_image(img_path)
                    used_image_ids.add(fig_id)

    def _render_markdown_table(self, table_lines: List[str], image_map: Dict[str, str], selected_image_ids: List[str]):
        """
        Parses Markdown table lines and creates an authentic, beautiful Microsoft Word Table!
        """
        parsed_rows = []
        for line in table_lines:
            # Skip separator line |---|---|
            if re.match(r'^\|[\s\-:]+(\|[\s\-:]+)+\|$', line):
                continue
            # Extract cell values and clean accidental \text{...}
            cells = [c.strip() for c in line.strip('|').split('|')]
            cells = [re.sub(r'\\text\{([^}]+)\}', r'\1', c) for c in cells]
            parsed_rows.append(cells)

        if not parsed_rows:
            return

        col_count = max(len(r) for r in parsed_rows)
        # Pad shorter rows
        for r in parsed_rows:
            while len(r) < col_count:
                r.append("")

        # Check if table is a 2-column Exam Header (Logo / School name on left, Exam title on right)
        is_exam_header = False
        if len(parsed_rows) == 1 and col_count == 2:
            row_concat = " ".join(parsed_rows[0]).lower()
            if any(k in row_concat for k in ["trung tâm", "bài thi", "đề thi", "môn:", "thời gian", "học kì"]):
                is_exam_header = True

        table = self.doc.add_table(rows=len(parsed_rows), cols=col_count)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        if is_exam_header:
            table.style = None
            tblPr = table._tbl.tblPr
            borders = parse_xml(f'''
                <w:tblBorders {nsdecls("w")}>
                    <w:top w:val="none"/><w:left w:val="none"/>
                    <w:bottom w:val="none"/><w:right w:val="none"/>
                    <w:insideH w:val="none"/><w:insideV w:val="none"/>
                </w:tblBorders>
            ''')
            tblPr.append(borders)
            col_widths = [Inches(3.3), Inches(3.5)]
        else:
            table.style = 'Table Grid'
            # 3-column marking scheme table: Câu (0.9") | Đáp án (5.0") | Điểm (0.9")
            if col_count == 3:
                col_widths = [Inches(0.9), Inches(5.0), Inches(0.9)]
            else:
                col_widths = [Inches(6.8 / col_count)] * col_count

        for row_idx, row_data in enumerate(parsed_rows):
            is_header = (row_idx == 0 and not is_exam_header)
            tr = table.rows[row_idx]._tr
            # Repeat header row across pages if multi-page
            if is_header:
                trPr = tr.get_or_add_trPr()
                trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))

            for col_idx, cell_value in enumerate(row_data):
                cell = table.cell(row_idx, col_idx)
                cell.width = col_widths[min(col_idx, len(col_widths) - 1)]
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

                # Background shading for header
                if is_header:
                    tcPr = cell._tc.get_or_add_tcPr()
                    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="F2F2F2"/>'))

                # Clear default empty paragraph
                p = cell.paragraphs[0]
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.space_before = Pt(2)

                # Center align column 0 (Câu) and last column (Điểm), or header
                if is_header or is_exam_header or col_idx == 0 or (col_count == 3 and col_idx == 2):
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                else:
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

                # Split cell text by HTML line breaks <br>
                parts = re.split(r'<br\s*/?>', cell_value, flags=re.IGNORECASE)
                for p_idx, part in enumerate(parts):
                    clean_part = part.strip()
                    if not clean_part and p_idx > 0:
                        continue
                    if p_idx == 0:
                        cur_p = p
                    else:
                        cur_p = cell.add_paragraph()
                        cur_p.paragraph_format.line_spacing = 1.15
                        cur_p.paragraph_format.space_after = Pt(2)
                        cur_p.paragraph_format.space_before = Pt(2)
                        if is_header or is_exam_header or col_idx == 0 or (col_count == 3 and col_idx == 2):
                            cur_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

                    # Check for [HINH_X] inside table cell
                    fig_match = re.search(r'\[(HINH_\w+)\]', clean_part)
                    if fig_match:
                        before_t = clean_part[:fig_match.start()].strip()
                        if before_t:
                            self._format_text_with_math_and_bold(cur_p, before_t, is_bold_all=(is_header or is_exam_header))

                        fig_id = fig_match.group(1)
                        if fig_id in image_map and (selected_image_ids is None or fig_id in selected_image_ids):
                            img_path = image_map[fig_id]
                            if os.path.exists(img_path):
                                img_p = cell.add_paragraph() if before_t else cur_p
                                img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                                img_p.paragraph_format.line_spacing = 1.0
                                img_p.paragraph_format.space_before = Pt(2)
                                img_p.paragraph_format.space_after = Pt(2)
                                run_pic = img_p.add_run()
                                run_pic.add_picture(img_path, width=Inches(3.0))

                        after_t = clean_part[fig_match.end():].strip()
                        if after_t:
                            after_p = cell.add_paragraph()
                            after_p.paragraph_format.line_spacing = 1.15
                            after_p.paragraph_format.space_before = Pt(2)
                            after_p.paragraph_format.space_after = Pt(2)
                            self._format_text_with_math_and_bold(after_p, after_t, is_bold_all=(is_header or is_exam_header))
                    else:
                        self._format_text_with_math_and_bold(cur_p, clean_part, is_bold_all=(is_header or is_exam_header))

        # Space after table
        sp_after = self.doc.add_paragraph()
        sp_after.paragraph_format.space_before = Pt(4)
        sp_after.paragraph_format.space_after = Pt(0)

    def _try_parse_multiple_choice(self, lines: List[str], start_idx: int) -> Optional[Tuple[List[str], int]]:
        """
        Detects if lines starting at start_idx form a 4-option multiple choice set (A, B, C, D).
        Returns (list_of_4_options, next_line_index) or None.
        """
        line = lines[start_idx].strip()
        if not line:
            return None

        # Check if this line starts with an option A marker (including bold and underline)
        a_match = re.match(r'^(?:[-*•]\s+)?(?:\*\*|\*)?(?:<u>|\\underline\{)?(?:\()?A[\.:\)](?:</u>|\})?(?:\*\*|\*)?\s+', line)
        if not a_match:
            return None

        gathered_lines = []
        collected_indices = []

        stop_pattern = re.compile(
            r'^(?:#|\||\[HINH_\w+\]|(?:\*\*)?(?:Câu|Bài|Khẳng định|Phần|PHẦN|ĐỀ|BÀI|Ví dụ)\s+\d+)',
            re.IGNORECASE
        )
        opt_marker_pattern = re.compile(
            r'(?:^|(?<=\s)|(?<=\$\s)|(?<=\\quad\s)|(?<=\t))(?:\*\*|\*)?(?:<u>|\\underline\{)?([A-D])[\.:\)](?:</u>|\})?(?:\*\*|\*)?\s+'
        )

        j = start_idx
        while j < len(lines):
            cur_line = lines[j].strip()
            if not cur_line:
                j += 1
                continue

            # If encountering a heading, question header, or table before seeing D, abort
            if j > start_idx and stop_pattern.search(cur_line):
                break

            gathered_lines.append(cur_line)
            collected_indices.append(j)

            # Check if D has been reached
            combined_text = "\n".join(gathered_lines)
            matches = list(opt_marker_pattern.finditer(combined_text))
            letters = [m.group(1) for m in matches]
            if 'D' in letters:
                break

            if len(gathered_lines) > 8:
                break

            j += 1

        if not gathered_lines:
            return None

        full_text = "\n".join(gathered_lines)
        matches = list(opt_marker_pattern.finditer(full_text))
        letters = [m.group(1) for m in matches]

        if letters != ['A', 'B', 'C', 'D']:
            return None

        options = []
        for k in range(4):
            st = matches[k].start()
            en = matches[k+1].start() if k < 3 else len(full_text)
            opt_str = full_text[st:en].strip()
            # Clean trailing separators ($\quad$, \quad, tabs)
            opt_str = re.sub(r'(\$\\quad\$|\\quad|\\qquad|\t|\s)+$', '', opt_str).strip()
            # Check if this option is underlined (e.g. McMix correct answer)
            is_under = bool(re.search(r'<u>|\\underline\{', opt_str[:25]))
            pref = re.match(r'^(?:[-*•]\s+)?(?:\*\*|\*)?(?:<u>|\\underline\{)?(?:\()?([A-D])[\.:\)](?:</u>|\})?(?:\*\*|\*)?\s*', opt_str)
            if pref:
                let = pref.group(1)
                cnt = opt_str[pref.end():].strip()

                # 1. Strip outer underline from option content
                cnt = re.sub(r'^<u>\s*', '', cnt)
                cnt = re.sub(r'\s*</u>$', '', cnt)
                cnt = re.sub(r'^\\underline\{\s*', '', cnt)
                cnt = re.sub(r'\s*\}$', '', cnt)

                # 2. Clean redundant option label inside math: e.g. $\text{B. } 2x^2y + 1$ or $\text{A. } 5$
                def clean_nested_label(m):
                    inner = m.group(1).strip()
                    inner = re.sub(r'^\\text\{\s*[A-D][\.:\)]\s*\}\s*', '', inner)
                    inner = re.sub(r'^\\text\{\s*[A-D][\.:\)]\s*(.*?)\}', r'\\text{\1}', inner)
                    if not inner.strip():
                        return ""
                    # If inner is plain Vietnamese text (not math formula), unwrap it
                    unwrapped = re.sub(r'\\text\{([^}]+)\}', r'\1', inner)
                    if not re.search(r'\\(frac|dfrac|sqrt|sum|int|sin|cos|tan|cot|alpha|beta|pi|partial|cdot|times|le|ge|ne|pm|circ)', unwrapped):
                        if LatexFormatter.VN_REGEX.search(unwrapped) and (' ' in unwrapped or len(unwrapped) > 3):
                            return unwrapped
                    return f"${inner}$"

                cnt = re.sub(r'\$([^\$]+)\$', clean_nested_label, cnt).strip()
                # 3. Clean any stray ext[A-D]. prefix
                cnt = re.sub(r'^\s*ext[A-D][\.:\)]\s*', '', cnt)

                if is_under:
                    opt_str = f"**<u>{let}.</u>** {cnt}"
                else:
                    opt_str = f"**{let}.** {cnt}"
            options.append(opt_str)

        next_idx = collected_indices[-1] + 1
        return options, next_idx

    def _calc_option_length(self, opt_text: str) -> int:
        """Estimates readable character length of an option by stripping LaTeX and markup."""
        t = re.sub(r'^\*\*[A-D]\.\*\*\s*', '', opt_text)
        t = t.replace('$', '')
        t = re.sub(r'\\[a-zA-Z]+', '', t)
        t = re.sub(r'[\{\}\^_\\]', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return len(t)

    def _is_question_start(self, line: str) -> bool:
        """Determines if a line looks like the start of an exam question or problem."""
        return bool(QUESTION_START_RE.match(line.strip()))

    def _is_option_start(self, line: str) -> bool:
        """Determines if a line looks like the start of a multiple-choice option (A., B., etc.)."""
        return bool(OPTION_START_RE.match(line.strip()))

    def _is_solution_start(self, line: str) -> bool:
        """Determines if a line looks like the start of a solution or explanation."""
        return bool(SOLUTION_START_RE.match(line.strip()))

    def _try_render_side_by_side_question_figure(
        self,
        lines: List[str],
        start_idx: int,
        image_map: Dict[str, str],
        selected_image_ids: List[str],
        used_image_ids: set
    ) -> Optional[int]:
        """
        Attempts to render a question prompt and its associated figure side-by-side using
        a borderless 2-column Word table (Left: question prompt, Right: diagram/figure).
        Follows standard Ministry of Education exam format (Smart Fluid Layout).
        Returns the line index to resume parsing from, or None if standard rendering is used.
        """
        if not self.smart_layout:
            return None

        prompt_lines = []
        k = start_idx
        max_scan = min(len(lines), start_idx + 10)
        fig_found = False

        while k < max_scan:
            line_k = lines[k].strip()
            if not line_k:
                if fig_found:
                    # An empty line after a figure has been seen marks prompt completion
                    break
                k += 1
                continue

            # Stop if multiple choice options start
            if self._is_option_start(line_k) or (
                self.format_multiple_choice and self._try_parse_multiple_choice(lines, k) is not None
            ):
                break

            # Stop if the next question starts
            if k > start_idx and self._is_question_start(line_k):
                break

            # Stop if solution begins
            if self._is_solution_start(line_k):
                break

            # Stop if markdown table or heading begins
            if line_k.startswith("|") or line_k.startswith("#"):
                break

            if re.search(r'\[(HINH_\w+)\]', line_k):
                fig_found = True

            prompt_lines.append(line_k)
            k += 1

        if not prompt_lines:
            return None

        # Check for figure placeholders in prompt lines
        combined_text = " ".join(prompt_lines)
        fig_matches = re.findall(r'\[(HINH_\w+)\]', combined_text)
        if not fig_matches:
            return None

        unique_figs = list(dict.fromkeys(fig_matches))
        if len(unique_figs) != 1:
            # If multiple distinct figures, fall back to sequential full-width layout
            return None

        fig_id = unique_figs[0]
        if fig_id not in image_map or fig_id not in selected_image_ids:
            return None

        img_path = image_map[fig_id]
        if not os.path.exists(img_path):
            return None

        # Check aspect ratio
        img_w_px = 0
        img_h_px = 0
        try:
            from PIL import Image
            with Image.open(img_path) as im:
                img_w_px, img_h_px = im.size
                ar = img_w_px / img_h_px if img_h_px > 0 else 1.0
        except Exception:
            ar = 1.0

        if ar > 2.5:
            # Panoramic / wide banner: keep standard full-width layout
            return None

        # Clean prompt lines by stripping [HINH_X]
        clean_prompt_lines = []
        for pl in prompt_lines:
            cleaned = re.sub(r'\[HINH_\w+\]', '', pl).strip()
            cleaned = re.sub(r'\s{2,}', ' ', cleaned)
            if cleaned:
                clean_prompt_lines.append(cleaned)

        if not clean_prompt_lines:
            return None

        # Create borderless 2-column table
        table = self._create_borderless_table(rows=1, cols=2)
        cell_left = table.cell(0, 0)
        cell_right = table.cell(0, 1)

        # Standard page printable width = 6.69 inches
        # Left (Prompt): 4.35 inches (~65%)
        # Right (Figure): 2.34 inches (~35%)
        cell_left.width = Inches(4.35)
        cell_right.width = Inches(2.34)
        cell_left.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        cell_right.vertical_alignment = WD_ALIGN_VERTICAL.TOP

        # Render question prompt on Left
        for idx, text_line in enumerate(clean_prompt_lines):
            p = cell_left.paragraphs[0] if idx == 0 else cell_left.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_before = Pt(3 if idx == 0 else 1)
            p.paragraph_format.space_after = Pt(2)
            self._format_text_with_math_and_bold(p, text_line)

        # Render figure on Right
        p_img = cell_right.paragraphs[0]
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.line_spacing = 1.0
        p_img.paragraph_format.space_before = Pt(0)
        p_img.paragraph_format.space_after = Pt(2)

        try:
            run_img = p_img.add_run()
            # Constrain image within 2.2" width x 2.4" height
            if img_w_px > 0 and (img_h_px / img_w_px) > (2.4 / 2.2):
                run_img.add_picture(img_path, height=Inches(2.3))
            else:
                run_img.add_picture(img_path, width=Inches(2.2))
        except Exception:
            pass

        used_image_ids.add(fig_id)
        return k

    def _create_borderless_table(self, rows: int, cols: int):
        """Creates a completely borderless Microsoft Word table (hidden grid for perfect alignment)."""
        table = self.doc.add_table(rows=rows, cols=cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        tblPr = table._tbl.tblPr
        borders = parse_xml(f'''
            <w:tblBorders {nsdecls("w")}>
                <w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>
                <w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>
                <w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>
                <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>
                <w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>
                <w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>
            </w:tblBorders>
        ''')
        tblPr.append(borders)
        return table

    def _render_option_cell(
        self,
        cell,
        opt_text: str,
        col_width,
        image_map: Dict[str, str],
        selected_image_ids: List[str],
        used_image_ids: set
    ):
        """Renders an option into a table cell with native OMML math and optional images."""
        cell.width = col_width
        p = cell.paragraphs[0]
        p.paragraph_format.line_spacing = 1.15
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(2)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT

        fig_match = re.search(r'\[(HINH_\w+)\]', opt_text)
        if fig_match:
            fig_id = fig_match.group(1)
            used_image_ids.add(fig_id)
            before_text = opt_text[:fig_match.start()].strip()
            if before_text:
                self._format_text_with_math_and_bold(p, before_text)
            if fig_id in image_map and fig_id in selected_image_ids:
                img_path = image_map[fig_id]
                if os.path.exists(img_path):
                    run = p.add_run()
                    img_w = Inches(1.3) if col_width < Inches(2.5) else Inches(2.2)
                    run.add_picture(img_path, width=img_w)
            after_text = opt_text[fig_match.end():].strip()
            if after_text:
                p2 = cell.add_paragraph()
                p2.paragraph_format.line_spacing = 1.15
                p2.paragraph_format.space_before = Pt(1)
                p2.paragraph_format.space_after = Pt(2)
                self._format_text_with_math_and_bold(p2, after_text)
        else:
            self._format_text_with_math_and_bold(p, opt_text)

    def _render_multiple_choice_table(
        self,
        options: List[str],
        image_map: Dict[str, str],
        selected_image_ids: List[str],
        used_image_ids: set
    ):
        """
        Renders 4 multiple-choice options (A, B, C, D) using a clean borderless Word table.
        Layout decision according to Ministry of Education & Training exam standards:
        - 1 row x 4 columns: when all options are short (max_len <= 15 and total_len <= 55)
        - 2 rows x 2 columns: when options are medium (max_len <= 38 and total_len <= 140)
        - 4 rows x 1 column: when options are long sentences/explanations
        """
        lengths = [self._calc_option_length(o) for o in options]
        max_len = max(lengths)
        total_len = sum(lengths)

        # 1 dòng 4 cột (4 columns x 1 row)
        if max_len <= 15 and total_len <= 55:
            table = self._create_borderless_table(rows=1, cols=4)
            col_w = Inches(1.67)
            for idx, opt in enumerate(options):
                self._render_option_cell(table.cell(0, idx), opt, col_w, image_map, selected_image_ids, used_image_ids)

        # 2 dòng 2 cột (2 columns x 2 rows)
        elif max_len <= 38 and total_len <= 140:
            table = self._create_borderless_table(rows=2, cols=2)
            col_w = Inches(3.34)
            # Row 0: A, B
            self._render_option_cell(table.cell(0, 0), options[0], col_w, image_map, selected_image_ids, used_image_ids)
            self._render_option_cell(table.cell(0, 1), options[1], col_w, image_map, selected_image_ids, used_image_ids)
            # Row 1: C, D
            self._render_option_cell(table.cell(1, 0), options[2], col_w, image_map, selected_image_ids, used_image_ids)
            self._render_option_cell(table.cell(1, 1), options[3], col_w, image_map, selected_image_ids, used_image_ids)

        # 4 dòng 1 cột (1 column x 4 rows)
        else:
            table = self._create_borderless_table(rows=4, cols=1)
            col_w = Inches(6.69)
            for idx, opt in enumerate(options):
                self._render_option_cell(table.cell(idx, 0), opt, col_w, image_map, selected_image_ids, used_image_ids)

    def _format_text_with_math_and_bold(
        self,
        paragraph,
        text: str,
        is_heading: bool = False,
        heading_level: int = 1,
        is_bold_all: bool = False
    ):
        """
        Parses text for math formulas ($...$ and $$...$$) and bold tags (**text**).
        Converts math to real Word OMML equations!
        """
        # Split by display math ($$...$$) first, then inline math ($...$)
        tokens = re.split(r'(\$\$.*?\$\$|\$.*?\$)', text)

        for token in tokens:
            if not token:
                continue

            # Display math ($$...$$)
            if token.startswith("$$") and token.endswith("$$") and len(token) > 4:
                math_code = token[2:-2].strip()
                if self.convert_to_omml:
                    omml_elem = OMMLConverter.latex_to_omml(math_code)
                    if omml_elem is not None:
                        # Append equation directly
                        paragraph._p.append(omml_elem)
                        continue
                # Fallback to text
                run = paragraph.add_run(token)
                self._apply_run_font(run, is_heading, heading_level, is_bold_all)

            # Inline math ($...$)
            elif token.startswith("$") and token.endswith("$") and len(token) > 2:
                math_code = token[1:-1].strip()
                if self.convert_to_omml:
                    omml_elem = OMMLConverter.latex_to_omml(math_code)
                    if omml_elem is not None:
                        paragraph._p.append(omml_elem)
                        continue
                # Fallback to text
                run = paragraph.add_run(token)
                self._apply_run_font(run, is_heading, heading_level, is_bold_all)

            # Plain text with possible bold **...** and underline <u>...</u>
            else:
                sub_parts = re.split(r'(\*\*.*?\*\*|<u>.*?</u>)', token)
                for sp in sub_parts:
                    if not sp:
                        continue
                    is_bold = is_bold_all
                    is_under = False
                    val = sp

                    if val.startswith("**") and val.endswith("**") and len(val) >= 4:
                        is_bold = True
                        val = val[2:-2]

                    if val.startswith("<u>") and val.endswith("</u>") and len(val) >= 7:
                        is_under = True
                        val = val[3:-4]

                    if val.startswith("**") and val.endswith("**") and len(val) >= 4:
                        is_bold = True
                        val = val[2:-2]

                    un_m = re.match(r'^\\underline\{([^}]+)\}$', val)
                    if un_m:
                        is_under = True
                        val = un_m.group(1)

                    # Strip any stray HTML tags so they never appear literally in Word
                    val = re.sub(r'</?(?:u|b|i|strong|em|br\s*/?)>', '', val)
                    if not val:
                        continue

                    run = paragraph.add_run(val)
                    if is_bold:
                        run.bold = True
                    if is_under:
                        run.font.underline = True
                    self._apply_run_font(run, is_heading, heading_level, is_bold, is_under)

    def _apply_run_font(self, run, is_heading: bool, heading_level: int, is_bold_all: bool, is_underlined: bool = False):
        run.font.name = self.font_name
        if is_heading:
            run.bold = True
            run.font.size = Pt(self.font_size_pt + (2 if heading_level == 1 else 1))
            run.font.color.rgb = RGBColor(0, 32, 96)
        else:
            run.font.size = Pt(self.font_size_pt)
            run.font.color.rgb = RGBColor(0, 0, 0)
        if is_bold_all:
            run.bold = True
        if is_underlined:
            run.font.underline = True

    def _add_formatted_paragraph(self, text: str):
        p = self.doc.add_paragraph()
        self._format_text_with_math_and_bold(p, text)

    def _insert_image(self, image_path: str):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(6)
        try:
            # 3.0 inches (~7.6 cm) is optimal for geometry and diagrams in exam papers
            run = p.add_run()
            run.add_picture(image_path, width=Inches(3.0))
        except Exception:
            pass

    def save(self, output_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        self.doc.save(output_path)
        return output_path

    @staticmethod
    def trigger_word_toggle_tex(docx_path: str) -> bool:
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = True
            doc = word.Documents.Open(os.path.abspath(docx_path))
            try:
                word.Run("MathTypeCommands.ToggleTeX.Main")
                return True
            except Exception:
                try:
                    word.Run("ToggleTeX")
                    return True
                except Exception:
                    pass
            return False
        except Exception:
            return False
