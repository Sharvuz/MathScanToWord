import os
import cv2
import numpy as np
from PIL import Image
from typing import Optional, Tuple

class ImagePreprocessor:
    """
    Intelligent computer vision pre-processor for scanned or photographed Math/KHTN pages:
    - Background whitening & gutter shadow removal (removes yellow paper, spine folds, uneven light)
    - Auto-deskewing (straightens tilted scans with sub-degree accuracy)
    - Dynamic range contrast enhancement & sharpening (sharpens geometry diagrams & math symbols)
    """

    @staticmethod
    def pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
        return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)

    @staticmethod
    def cv2_to_pil(cv_img: np.ndarray) -> Image.Image:
        return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

    @classmethod
    def whiten_background(cls, cv_img: np.ndarray) -> np.ndarray:
        """
        Removes shadows, paper yellowing, gutter/spine gradients and uneven illumination.
        Preserves thin math symbols, geometry lines, dotted lines, and colored diagrams.
        """
        is_color = (len(cv_img.shape) == 3)
        if is_color:
            lab = cv2.cvtColor(cv_img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            gray = l
        else:
            gray = cv_img

        h, w = gray.shape[:2]

        # Downscale to ~800px width for fast background illumination estimation (< 20ms)
        scale = 800.0 / max(w, 800)
        if scale < 1.0:
            small_gray = cv2.resize(gray, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        else:
            small_gray = gray

        sh, sw = small_gray.shape[:2]
        k_size = max(25, (min(sh, sw) // 30) | 1)  # must be odd
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))

        # Morphological closing estimates background surface
        bg_small = cv2.morphologyEx(small_gray, cv2.MORPH_CLOSE, kernel)
        bg_small = cv2.GaussianBlur(bg_small, (k_size, k_size), 0)

        # Upscale background surface back to full resolution
        if scale < 1.0:
            bg = cv2.resize(bg_small, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            bg = bg_small

        # Illumination division: (gray / bg) * 255
        bg = np.maximum(bg, 1)
        diff = cv2.divide(gray, bg, scale=255.0)

        # Dynamic range stretch
        norm = cv2.normalize(diff, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)

        # Level curves: paper background (>225) -> pure white 255, deep text (<35) -> 0
        lut = np.zeros(256, dtype=np.uint8)
        for i in range(256):
            if i >= 225:
                lut[i] = 255
            elif i <= 35:
                lut[i] = 0
            else:
                lut[i] = int(((i - 35) / (225 - 35)) * 255)

        enhanced_gray = cv2.LUT(norm, lut)

        # Subtle unsharp masking for crisp math & geometry
        blurred = cv2.GaussianBlur(enhanced_gray, (0, 0), 2.0)
        sharpened = cv2.addWeighted(enhanced_gray, 1.20, blurred, -0.20, 0)

        if is_color:
            enhanced_lab = cv2.merge([sharpened, a, b])
            return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        else:
            return sharpened

    @classmethod
    def estimate_skew_angle(cls, cv_img: np.ndarray) -> float:
        """
        Fast and robust text orientation angle detection.
        Downscales for high speed, detects horizontal text line contours,
        and computes median orientation angle.
        """
        if len(cv_img.shape) == 3:
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = cv_img

        h, w = gray.shape[:2]
        scale = 1000.0 / max(w, 1000)
        if scale < 1.0:
            small_gray = cv2.resize(gray, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        else:
            small_gray = gray

        sw = small_gray.shape[1]
        thresh = cv2.threshold(small_gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

        # Dilate horizontally to connect text characters into lines
        kernel_w = max(15, int(sw * 0.025))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 3))
        dilated = cv2.dilate(thresh, kernel, iterations=1)

        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        angles = []
        for c in contours:
            if cv2.contourArea(c) < 150:
                continue
            rect = cv2.minAreaRect(c)
            (rw, rh) = rect[1]
            if rw < 30 or rh < 6:
                continue

            angle = rect[2]
            # Normalize angle to range [-45, 45]
            if angle < -45:
                angle = -(90 + angle)
            elif angle > 45:
                angle = 90 - angle
            else:
                angle = -angle

            if abs(angle) <= 15.0:
                angles.append(angle)

        if not angles:
            return 0.0

        return float(np.median(angles))

    @classmethod
    def detect_and_fix_orientation(cls, cv_img: np.ndarray) -> Tuple[np.ndarray, int]:
        """
        Tự động phát hiện hướng trang scan bị xoay dọc/ngang (90°, 180°, 270°).
        Sử dụng phân tích hướng các dải dòng văn bản (morphological text line linking)
        và mật độ lề để tự động xoay thẳng đứng (Upright) trước khi gửi cho AI.
        Trả về (upright_cv_img, rotated_degrees).
        """
        h, w = cv_img.shape[:2]
        scale = 1000.0 / max(h, 1)
        img_std = cv2.resize(cv_img, (max(10, int(w * scale)), 1000), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(img_std, cv2.COLOR_BGR2GRAY) if len(img_std.shape) == 3 else img_std
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

        # 1. Đếm dải dòng chữ ngang
        kh = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 3))
        dil_h = cv2.dilate(thresh, kh, iterations=1)
        cnts_h, _ = cv2.findContours(dil_h, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        long_h = sum(1 for c in cnts_h if cv2.boundingRect(c)[2] > cv2.boundingRect(c)[3] * 2.8 and cv2.boundingRect(c)[2] > 60)

        # 2. Đếm dải dòng chữ dọc
        kv = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 35))
        dil_v = cv2.dilate(thresh, kv, iterations=1)
        cnts_v, _ = cv2.findContours(dil_v, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        long_v = sum(1 for c in cnts_v if cv2.boundingRect(c)[3] > cv2.boundingRect(c)[2] * 2.8 and cv2.boundingRect(c)[3] > 60)

        # Nếu số dòng dọc áp đảo số dòng ngang -> Trang đang bị xoay ngang/dọc (90° hoặc 270°)
        if long_v >= 15 and long_v > long_h * 1.8:
            test_ccw = cv2.rotate(thresh, cv2.ROTATE_90_COUNTERCLOCKWISE)
            th_h, th_w = test_ccw.shape
            left_d = np.sum(test_ccw[:, :int(th_w * 0.25)])
            right_d = np.sum(test_ccw[:, int(th_w * 0.75):])
            ratio_ccw = left_d / max(1.0, right_d)

            if ratio_ccw >= 0.95:
                # Xoay 90° ngược chiều kim đồng hồ
                return cv2.rotate(cv_img, cv2.ROTATE_90_COUNTERCLOCKWISE), 270
            else:
                # Xoay 90° thuận chiều kim đồng hồ
                return cv2.rotate(cv_img, cv2.ROTATE_90_CLOCKWISE), 90

        return cv_img, 0

    @classmethod
    def deskew(cls, cv_img: np.ndarray, angle: Optional[float] = None) -> Tuple[np.ndarray, float]:
        """Rotates the image straight around its center."""
        if angle is None:
            angle = cls.estimate_skew_angle(cv_img)

        # Skip rotation if angle is tiny (< 0.25 deg) to prevent resampling blur
        if abs(angle) < 0.25:
            return cv_img, 0.0

        h, w = cv_img.shape[:2]
        center = (w // 2, h // 2)
        # Note: In OpenCV warpAffine, positive angle rotates counter-clockwise.
        # minAreaRect angle: if tilted by +3.5 deg, rotating by -3.5 deg straightens it.
        M = cv2.getRotationMatrix2D(center, -angle, 1.0)
        rotated = cv2.warpAffine(
            cv_img, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255) if len(cv_img.shape) == 3 else 255
        )
        return rotated, angle

    @classmethod
    def enhance_page(
        cls,
        pil_img: Image.Image,
        deskew: bool = True,
        whiten: bool = True,
        auto_rotate: bool = True
    ) -> Tuple[Image.Image, float]:
        """
        Complete enhancement pipeline for a scanned/photographed document page:
        1. Auto-detect orientation and rotate upright (90°/270°)
        2. Whiten background and remove gutter shadows
        3. Detect fine skew angle and deskew straight
        Returns (enhanced_pil_img, detected_angle)
        """
        cv_img = cls.pil_to_cv2(pil_img)
        rot_deg = 0

        # Step 0: Auto-detect and fix 90/270 degree sideways page scans
        if auto_rotate:
            cv_img, rot_deg = cls.detect_and_fix_orientation(cv_img)

        # Step 1: Whiten background first so shadows don't interfere with skew detection
        if whiten:
            cv_img = cls.whiten_background(cv_img)

        # Step 2: Detect skew angle on the clean image and rotate straight
        detected_angle = float(rot_deg)
        if deskew:
            cv_img, fine_angle = cls.deskew(cv_img)
            detected_angle += fine_angle

        return cls.cv2_to_pil(cv_img), detected_angle

    @classmethod
    def detect_two_column_layout(cls, cv_img: np.ndarray) -> Tuple[bool, Optional[int]]:
        """
        Detects if a scanned document page has a two-column vertical layout.
        Uses vertical divider line detection and vertical projection gutter analysis.
        Returns: (is_two_column, split_x_in_original_coords)
        """
        h, w = cv_img.shape[:2]
        if w < 300 or h < 300:
            return False, None

        # Work on a standard width (~800px) for consistent and fast analysis (< 10ms)
        scale = 800.0 / float(w)
        sw = 800
        sh = int(h * scale)
        small = cv2.resize(cv_img, (sw, sh), interpolation=cv2.INTER_AREA)

        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY) if len(small.shape) == 3 else small

        # Otsu threshold (inverted: text is white, background is black)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

        # Ignore top 8% (headers) and bottom 8% (footers)
        y_start = int(sh * 0.08)
        y_end = int(sh * 0.92)
        roi_thresh = thresh[y_start:y_end, :]
        roi_h = y_end - y_start

        # Central search region for column divider/gutter: x in [35%, 65%]
        cx_min = int(sw * 0.35)
        cx_max = int(sw * 0.65)

        # 1. Check for explicit vertical divider line
        vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 35))
        vert_lines = cv2.morphologyEx(roi_thresh[:, cx_min:cx_max], cv2.MORPH_OPEN, vert_kernel)
        col_sums_lines = np.sum(vert_lines, axis=0) / 255.0

        max_line_len = np.max(col_sums_lines) if len(col_sums_lines) > 0 else 0
        if max_line_len >= roi_h * 0.35:
            best_rel_x = int(np.argmax(col_sums_lines))
            split_x_small = cx_min + best_rel_x
            split_x_orig = int(split_x_small / scale)
            return True, split_x_orig

        # 2. Check for vertical whitespace gutter (gap between two columns of text)
        word_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3))
        dilated_text = cv2.dilate(roi_thresh, word_kernel, iterations=1)

        vert_proj = np.sum(dilated_text > 0, axis=0)

        left_density = np.mean(vert_proj[int(sw * 0.10) : cx_min])
        right_density = np.mean(vert_proj[cx_max : int(sw * 0.90)])

        if left_density < roi_h * 0.12 or right_density < roi_h * 0.12:
            return False, None

        central_proj = vert_proj[cx_min:cx_max]
        min_val = np.min(central_proj)

        avg_density = (left_density + right_density) / 2.0
        if min_val < max(5, roi_h * 0.05) and min_val < avg_density * 0.25:
            gutter_mask = (central_proj <= min_val + roi_h * 0.03)
            gutter_width = np.sum(gutter_mask)
            if gutter_width >= 8:
                gutter_indices = np.where(gutter_mask)[0]
                center_gutter_rel = int(np.median(gutter_indices))
                split_x_small = cx_min + center_gutter_rel
                split_x_orig = int(split_x_small / scale)
                return True, split_x_orig

        return False, None

    @classmethod
    def split_two_columns(
        cls,
        pil_img: Image.Image,
        split_x: Optional[int] = None,
        overlap_px: int = 10
    ) -> Tuple[Image.Image, Image.Image, int]:
        """
        Splits a two-column document page into Left and Right column images.
        Includes a subtle overlap to ensure no characters on the boundary are truncated.
        Returns: (left_pil, right_pil, actual_split_x)
        """
        w, h = pil_img.size
        if split_x is None:
            cv_img = cls.pil_to_cv2(pil_img)
            is_2col, detected_split_x = cls.detect_two_column_layout(cv_img)
            split_x = detected_split_x if (is_2col and detected_split_x) else (w // 2)

        # Ensure split_x is within reasonable bounds [30%, 70%]
        split_x = max(int(w * 0.30), min(int(w * 0.70), split_x))

        # Crop Left column: 0 to split_x + overlap
        left_box = (0, 0, min(w, split_x + overlap_px), h)
        left_img = pil_img.crop(left_box)

        # Crop Right column: split_x - overlap to w
        right_box = (max(0, split_x - overlap_px), 0, w, h)
        right_img = pil_img.crop(right_box)

        return left_img, right_img, split_x


