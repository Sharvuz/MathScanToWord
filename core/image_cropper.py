import os
import cv2
import numpy as np
from PIL import Image
from typing import List, Dict, Any, Tuple, Optional, Union

class ImageCropper:
    """
    Bộ cắt ảnh thông minh tích hợp thị giác máy tính & OpenCV:
    1. Hút viền nét vẽ tự động (Smart Contour Auto-Snap):
       - Mở rộng vùng quét an toàn (Search Margin) để khôi phục các đỉnh (A, B, C) bị cắt hụt.
       - Tách và loại bỏ các dòng chữ đề bài hoặc tiêu đề trang bị cắt dính (Text Line Stripping).
       - Phân tích thành phần liên thông (Connected Components) để hút nam châm ôm sát viền nét vẽ và nhãn đỉnh.
       - Bổ sung khoảng thở cân đối (Safe Padding).
    2. Bộ lọc hình rỗng (Blank / Noise Rejector):
       - Nhận diện và loại bỏ các khung cắt chỉ có giấy trắng, hạt bụi, hoặc đường kẻ phân cách vô nghĩa.
    """

    @classmethod
    def is_blank_or_noise(cls, img_or_path: Union[str, Image.Image, np.ndarray]) -> Tuple[bool, str]:
        """
        Kiểm tra ảnh cắt có phải là hình rỗng, nhiễu scan, hay đường kẻ rác hay không:
        - Kích thước < 30px -> Rỗng/nhiễu.
        - Tỉ lệ quá dẹt (> 14:1) và bề ngang/dọc nhỏ -> Đường kẻ mép trang.
        - Số pixel mực đen < 60 hoặc tỉ lệ mực < 0.12% -> Khung trắng không có hình.
        - Mực đen > 88% -> Vết đen bóng gáy scan.
        - Số pixel cạnh Canny < 45 -> Không có nét vẽ hình học/đồ thị.
        Trả về (is_blank: bool, reason: str).
        """
        if isinstance(img_or_path, str):
            if not os.path.exists(img_or_path):
                return True, "File ảnh không tồn tại"
            try:
                with Image.open(img_or_path) as pil_im:
                    cv_img = cv2.cvtColor(np.array(pil_im.convert("RGB")), cv2.COLOR_RGB2BGR)
            except Exception as e:
                return True, f"Lỗi đọc ảnh: {e}"
        elif isinstance(img_or_path, Image.Image):
            cv_img = cv2.cvtColor(np.array(img_or_path.convert("RGB")), cv2.COLOR_RGB2BGR)
        elif isinstance(img_or_path, np.ndarray):
            cv_img = img_or_path
        else:
            return True, "Định dạng ảnh không hợp lệ"

        h, w = cv_img.shape[:2]
        if w < 30 or h < 30:
            return True, f"Kích thước quá nhỏ ({w}x{h} px < 30px)"

        aspect = max(w / max(h, 1), h / max(w, 1))
        if aspect > 7.0 and min(w, h) < 60:
            return True, f"Đường kẻ đơn / vết nhiễu mép trang (tỉ lệ {aspect:.1f}:1)"

        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img

        dark_mask = (gray < 200).astype(np.uint8)
        dark_pixels = int(np.sum(dark_mask))
        total_pixels = w * h
        ink_ratio = dark_pixels / max(total_pixels, 1)

        if dark_pixels < 60:
            return True, f"Hình rỗng (chỉ có {dark_pixels} pixel mực < 60)"

        if ink_ratio < 0.0012:
            return True, f"Mật độ nét quá thưa ({ink_ratio * 100:.2f}% < 0.12%)"

        if ink_ratio > 0.88:
            return True, f"Khung đen đặc / bóng gáy scan ({ink_ratio * 100:.1f}% mực)"

        edges = cv2.Canny(gray, 40, 140)
        edge_pixels = int(np.sum(edges > 0))

        if edge_pixels < 45:
            return True, f"Không có nét vẽ / cấu trúc hình học (chỉ có {edge_pixels} pixel cạnh)"

        return False, "Hình hợp lệ"

    @classmethod
    def refine_pixel_box(
        cls,
        page_image: Image.Image,
        pixel_box: Tuple[int, int, int, int]
    ) -> Tuple[int, int, int, int]:
        """
        Thuật toán Hút viền nét vẽ tự động (Smart Contour Auto-Snap):
        1. Mở rộng vùng tìm kiếm (Search Margin) 3.5% để thu hồi các nhãn đỉnh (A, B, C...) bị AI cắt hụt.
        2. Quét biểu đồ chiếu ngang (Horizontal Projection) phát hiện ranh giới chữ thừa ở mép trên/dưới.
        3. Phân tích thành phần liên thông (Connected Components) hút khít vào các nét vẽ hình học và nhãn đỉnh.
        4. Thêm khoảng thở an toàn (Safe Padding) 10-15px cân đối.
        """
        width, height = page_image.size
        left, top, right, bottom = pixel_box
        bw = right - left
        bh = bottom - top

        # 1. Mở rộng vùng tìm kiếm an toàn (min 18px, max 45px) để không bao giờ bỏ sót đỉnh nhọn hoặc nhãn A, B, C
        search_x = max(18, min(45, int(bw * 0.035)))
        search_y = max(18, min(45, int(bh * 0.035)))

        exp_l = max(0, left - search_x)
        exp_t = max(0, top - search_y)
        exp_r = min(width, right + search_x)
        exp_b = min(height, bottom + search_y)

        roi_crop = page_image.crop((exp_l, exp_t, exp_r, exp_b))
        rw, rh = roi_crop.size
        if rw < 30 or rh < 30:
            return pixel_box

        arr = np.array(roi_crop.convert("L"))
        dark = (arr < 195).astype(np.uint8)

        # 2. Phân tích biểu đồ chiếu ngang loại bỏ dòng chữ đề bài ở mép trên/dưới
        row_sums = np.sum(dark, axis=1)
        row_thresh = max(6, int(rw * 0.005))

        blocks = []
        in_b = False
        st = 0
        for y, count in enumerate(row_sums):
            if count >= row_thresh:
                if not in_b:
                    st = y
                    in_b = True
            else:
                if in_b:
                    blocks.append((st, y - 1, y - st))
                    in_b = False
        if in_b:
            blocks.append((st, rh - 1, rh - st))

        if not blocks:
            return pixel_box

        max_idx = max(range(len(blocks)), key=lambda i: blocks[i][2])
        main_h = blocks[max_idx][2]
        min_gap = max(8, int(rh * 0.012))

        cut_top = 0
        for i in range(max_idx):
            b_st, b_en, b_h = blocks[i]
            next_st = blocks[i + 1][0]
            gap = next_st - b_en
            if gap >= min_gap and (b_h < int(rh * 0.22) or b_h < int(main_h * 0.35)):
                cut_top = next_st

        cut_bottom = rh
        for i in range(len(blocks) - 1, max_idx, -1):
            b_st, b_en, b_h = blocks[i]
            prev_en = blocks[i - 1][1]
            gap = b_st - prev_en
            if gap >= min_gap and (b_h < int(rh * 0.22) or b_h < int(main_h * 0.35)):
                cut_bottom = prev_en + 1

        # 3. Phân tích thành phần liên thông (Connected Components) hút viền
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(dark, connectivity=8)

        diagram_boxes = []
        for i in range(1, num_labels):
            cx = stats[i, cv2.CC_STAT_LEFT]
            cy = stats[i, cv2.CC_STAT_TOP]
            cw = stats[i, cv2.CC_STAT_WIDTH]
            ch = stats[i, cv2.CC_STAT_HEIGHT]
            c_area = stats[i, cv2.CC_STAT_AREA]

            # Bỏ qua hạt bụi lấm tấm
            if c_area < 4:
                continue

            center_y = cy + ch / 2.0
            # Chỉ thu nạp các nét vẽ & nhãn nằm trong khoảng nội dung hợp lệ
            if center_y >= cut_top and center_y <= cut_bottom:
                diagram_boxes.append((cx, cy, cx + cw, cy + ch))

        if not diagram_boxes:
            return pixel_box

        snap_l = min(b[0] for b in diagram_boxes)
        snap_t = min(b[1] for b in diagram_boxes)
        snap_r = max(b[2] for b in diagram_boxes)
        snap_b = max(b[3] for b in diagram_boxes)

        # 4. Khoảng thở an toàn (Safe Padding)
        pad = max(10, int(min(bw, bh) * 0.015))
        final_l = max(0, exp_l + snap_l - pad)
        final_t = max(0, exp_t + max(cut_top, snap_t - pad))
        final_r = min(width, exp_l + snap_r + pad)
        final_b = min(height, exp_t + min(cut_bottom, snap_b + pad))

        return (int(final_l), int(final_t), int(final_r), int(final_b))

    @classmethod
    def crop_figure(
        cls,
        page_image: Image.Image,
        box_2d: List[float],
        output_path: str,
        padding: int = 5,
        auto_refine: bool = True
    ) -> Tuple[str, List[float]]:
        """
        Cắt hình vẽ từ page_image với tọa độ chuẩn hóa box_2d [ymin, xmin, ymax, xmax].
        Tự động tinh chỉnh viền (auto_refine=True) để loại bỏ chữ thừa và ôm sát nét vẽ.
        Trả về (đường_dẫn_ảnh_đã_cắt, tọa_độ_box_2d_đã_tinh_chỉnh).
        """
        width, height = page_image.size
        ymin, xmin, ymax, xmax = box_2d

        # Phát hiện tỉ lệ (0..1000 hay 0..1)
        scale_y = height / 1000.0 if max(ymin, xmin, ymax, xmax) > 1.0 else height
        scale_x = width / 1000.0 if max(ymin, xmin, ymax, xmax) > 1.0 else width

        top = max(0, int(ymin * scale_y))
        left = max(0, int(xmin * scale_x))
        bottom = min(height, int(ymax * scale_y))
        right = min(width, int(xmax * scale_x))

        if right <= left or bottom <= top:
            top, left, bottom, right = 0, 0, min(100, height), min(100, width)

        # Áp dụng bộ lọc thị giác máy tính tinh chỉnh viền
        if auto_refine:
            left, top, right, bottom = cls.refine_pixel_box(page_image, (left, top, right, bottom))

        cropped = page_image.crop((left, top, right, bottom))
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cropped.save(output_path, "PNG", quality=95)

        # Tính toán lại box_2d chuẩn hóa 0..1000 sau khi tinh chỉnh
        refined_box_2d = [
            (top / height) * 1000.0,
            (left / width) * 1000.0,
            (bottom / height) * 1000.0,
            (right / width) * 1000.0
        ]

        return output_path, refined_box_2d

    @staticmethod
    def crop_pixel_box(
        page_image: Image.Image,
        pixel_box: Tuple[int, int, int, int],
        output_path: str
    ) -> str:
        """
        Cắt trực tiếp theo pixel (left, top, right, bottom).
        Dùng khi người dùng kéo thả khung trong bộ chỉnh sửa.
        """
        left, top, right, bottom = pixel_box
        width, height = page_image.size
        left = max(0, min(width - 1, int(left)))
        top = max(0, min(height - 1, int(top)))
        right = max(left + 1, min(width, int(right)))
        bottom = max(top + 1, min(height, int(bottom)))

        cropped = page_image.crop((left, top, right, bottom))
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cropped.save(output_path, "PNG", quality=95)
        return output_path

    @staticmethod
    def rotate_cropped_file(crop_path: str, angle: int = 90) -> bool:
        """
        Xoay file ảnh đã cắt trên đĩa theo góc (90 độ theo chiều kim đồng hồ, -90, 180).
        Cập nhật trực tiếp file PNG để Word và LaTeX tự động nhận ảnh chuẩn.
        """
        if not os.path.exists(crop_path):
            return False
        try:
            with Image.open(crop_path) as im:
                if angle == 90 or angle == -270:
                    rotated = im.transpose(Image.Transpose.ROTATE_270)  # 90 deg Clockwise
                elif angle == -90 or angle == 270:
                    rotated = im.transpose(Image.Transpose.ROTATE_90)   # 90 deg Counter-Clockwise
                elif angle == 180 or angle == -180:
                    rotated = im.transpose(Image.Transpose.ROTATE_180)  # 180 deg
                else:
                    rotated = im.rotate(-angle, expand=True)
                rotated.save(crop_path, "PNG", quality=95)
            return True
        except Exception:
            return False

