import os
import pymupdf as fitz
from PIL import Image
import io
from typing import List, Tuple, Optional

class PDFProcessor:
    @staticmethod
    def get_page_count(pdf_path: str) -> int:
        if pdf_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            return 1
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count

    @staticmethod
    def render_page_to_image(
        pdf_path: str,
        page_number: int,
        dpi: int = 250,
        save_path: Optional[str] = None,
        enhance: bool = False,
        auto_rotate: bool = True
    ) -> Image.Image:
        """
        Renders a single 1-based page number to PIL Image at high DPI.
        Optionally enhances scan with OpenCV (whitening, deskewing & auto-rotation).
        Saves to disk if save_path is provided.
        """
        if pdf_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            img = Image.open(pdf_path).convert("RGB")
            if enhance:
                from core.image_preprocessor import ImagePreprocessor
                img, _ = ImagePreprocessor.enhance_page(img, deskew=True, whiten=True, auto_rotate=auto_rotate)
            elif auto_rotate:
                from core.image_preprocessor import ImagePreprocessor
                cv_img = ImagePreprocessor.pil_to_cv2(img)
                cv_img, _ = ImagePreprocessor.detect_and_fix_orientation(cv_img)
                img = ImagePreprocessor.cv2_to_pil(cv_img)

            if save_path:
                os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                img.save(save_path, "PNG", quality=95)
            return img

        doc = fitz.open(pdf_path)
        if page_number < 1 or page_number > len(doc):
            doc.close()
            raise ValueError(f"Trang {page_number} không hợp lệ (tổng số trang: {len(doc)})")

        page = doc.load_page(page_number - 1)
        # 72 is standard PDF points per inch. 250 DPI provides sharp text for OCR without excessive megabytes
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        doc.close()

        if enhance:
            from core.image_preprocessor import ImagePreprocessor
            img, _ = ImagePreprocessor.enhance_page(img, deskew=True, whiten=True, auto_rotate=auto_rotate)
        elif auto_rotate:
            from core.image_preprocessor import ImagePreprocessor
            cv_img = ImagePreprocessor.pil_to_cv2(img)
            cv_img, _ = ImagePreprocessor.detect_and_fix_orientation(cv_img)
            img = ImagePreprocessor.cv2_to_pil(cv_img)

        if save_path:
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            img.save(save_path, "PNG", quality=95)

        return img

    @staticmethod
    def split_pdf(pdf_path: str, output_dir: str, pages_per_chunk: int = 30) -> List[str]:
        """
        Splits a large PDF into smaller PDF files of `pages_per_chunk` pages each.
        Returns a list of created file paths.
        """
        os.makedirs(output_dir, exist_ok=True)
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        created_files = []
        chunk_idx = 1
        
        for start_page in range(0, total_pages, pages_per_chunk):
            end_page = min(start_page + pages_per_chunk, total_pages)
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)
            
            output_filename = f"{base_name}_Phan_{chunk_idx:02d}_(Trang_{start_page+1}-{end_page}).pdf"
            output_path = os.path.join(output_dir, output_filename)
            new_doc.save(output_path)
            new_doc.close()
            created_files.append(output_path)
            chunk_idx += 1
            
        doc.close()
        return created_files

    @staticmethod
    def parse_page_ranges(range_str: str, total_pages: int) -> List[int]:
        """
        Parses strings like "1-30, 35, 40-50" into a sorted list of unique 1-based page numbers.
        If empty or "all", returns all pages [1..total_pages].
        """
        if not range_str or range_str.strip().lower() in ["all", "tất cả"]:
            return list(range(1, total_pages + 1))
            
        pages = set()
        parts = range_str.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                try:
                    start_str, end_str = part.split("-", 1)
                    start = int(start_str.strip())
                    end = int(end_str.strip())
                    if start > end:
                        start, end = end, start
                    for p in range(start, end + 1):
                        if 1 <= p <= total_pages:
                            pages.add(p)
                except ValueError:
                    pass
            else:
                try:
                    p = int(part)
                    if 1 <= p <= total_pages:
                        pages.add(p)
                except ValueError:
                    pass
                    
        result = sorted(list(pages))
        return result if result else list(range(1, total_pages + 1))
