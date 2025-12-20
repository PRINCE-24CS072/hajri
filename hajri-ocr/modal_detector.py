"""
Modal Detection and Cropping for Attendance Screenshots
Classical CV + OCR-assisted detection (NO heavy ML)
CPU-only, Render free tier compatible
"""
import re
from typing import Optional, Tuple, Dict
import numpy as np
import cv2
from paddleocr import PaddleOCR
import logging

logger = logging.getLogger(__name__)


class ModalDetector:
    """
    Detects and crops attendance modal from university portal screenshots
    
    Strategy:
    1. Run OCR on top 30% of image
    2. Find "Lecture Gross Attendance" header text
    3. Expand boundaries to find modal edges
    4. Crop and normalize
    
    CPU-only, deterministic, fast.
    """
    
    def __init__(self, ocr_engine: Optional[PaddleOCR] = None):
        """
        Initialize modal detector
        
        Args:
            ocr_engine: Reuse existing PaddleOCR instance (IMPORTANT for performance)
        """
        self.ocr_engine = ocr_engine
        
        # Detection parameters
        self.header_search_region = 0.30  # Top 30% of image
        self.header_patterns = [
            r'Lecture\s+Gross\s+Attendance',
            r'Gross\s+Attendance',
            r'Attendance.*Semester',
        ]
        
        # Boundary expansion parameters
        self.vertical_padding_ratio = 0.05  # 5% padding
        self.horizontal_padding_ratio = 0.03  # 3% padding
        self.min_modal_height_ratio = 0.40  # Modal should be at least 40% of image height
        self.max_modal_height_ratio = 0.95  # Modal should be at most 95% of image height
        
        # Footer detection keywords
        self.footer_keywords = [
            'charotar university',
            'powered by',
            'copyright',
            '©',
            'all rights reserved',
        ]
        
        # Normalization parameters
        self.target_width = 1280  # Fixed width after crop
        
        logger.info("ModalDetector initialized - CPU-only classical CV + OCR")
    
    def detect_and_crop_modal(self, image: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """
        Main pipeline: Detect modal, crop, normalize
        
        Args:
            image: Input screenshot (BGR format from cv2)
        
        Returns:
            (cropped_modal, debug_info)
            
        Raises:
            ValueError: If modal cannot be detected
        """
        original_height, original_width = image.shape[:2]
        debug_info = {
            'original_size': (original_width, original_height),
            'detection_method': None,
            'header_found': False,
            'crop_bounds': None,
        }
        
        logger.info(f"Detecting modal in {original_width}x{original_height} image")
        
        # Step 1: Detect header in top region
        header_bbox = self._detect_header(image)
        
        if header_bbox is None:
            logger.warning("Header not found, falling back to heuristic detection")
            # Fallback: Use heuristic modal detection
            crop_bounds = self._detect_modal_heuristic(image)
            debug_info['detection_method'] = 'heuristic'
        else:
            logger.info(f"Header detected at Y={header_bbox[1]}")
            debug_info['header_found'] = True
            debug_info['header_bbox'] = header_bbox
            
            # Step 2: Expand boundaries from header
            crop_bounds = self._expand_modal_boundaries(image, header_bbox)
            debug_info['detection_method'] = 'ocr_anchor'
        
        if crop_bounds is None:
            raise ValueError("Modal detection failed - could not find attendance modal boundaries")
        
        x1, y1, x2, y2 = crop_bounds
        debug_info['crop_bounds'] = crop_bounds
        
        # Validate crop bounds
        crop_width = x2 - x1
        crop_height = y2 - y1
        
        if crop_width < 400 or crop_height < 300:
            raise ValueError(f"Detected modal too small: {crop_width}x{crop_height}px")
        
        logger.info(f"Modal detected: ({x1},{y1}) to ({x2},{y2}) = {crop_width}x{crop_height}px")
        
        # Step 3: Crop modal
        cropped = image[y1:y2, x1:x2].copy()
        
        # Step 4: Normalize cropped modal
        normalized = self._normalize_modal(cropped)
        debug_info['normalized_size'] = normalized.shape[:2][::-1]
        
        logger.info(f"Modal cropped and normalized to {normalized.shape[1]}x{normalized.shape[0]}px")
        
        return normalized, debug_info
    
    def _detect_header(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect modal header using OCR on top region
        
        Returns:
            (x1, y1, x2, y2) bounding box of header text, or None
        """
        height, width = image.shape[:2]
        search_height = int(height * self.header_search_region)
        
        # Crop top region for faster OCR
        top_region = image[:search_height, :].copy()
        
        logger.info(f"Searching for header in top {search_height}px")
        
        # Run OCR on top region only
        if self.ocr_engine is None:
            logger.warning("No OCR engine provided, cannot detect header")
            return None
        
        try:
            result = self.ocr_engine.ocr(top_region, cls=False)
            
            if not result or not result[0]:
                logger.warning("No OCR results in top region")
                return None
            
            # Search for header pattern
            for line in result[0]:
                box = line[0]
                text = line[1][0].strip()
                
                # Check if text matches any header pattern
                text_upper = text.upper()
                for pattern in self.header_patterns:
                    if re.search(pattern, text_upper, re.IGNORECASE):
                        # Found header!
                        x1 = int(min(p[0] for p in box))
                        y1 = int(min(p[1] for p in box))
                        x2 = int(max(p[0] for p in box))
                        y2 = int(max(p[1] for p in box))
                        
                        logger.info(f"Header found: '{text}' at ({x1},{y1})")
                        return (x1, y1, x2, y2)
            
            logger.warning("Header text pattern not found in OCR results")
            return None
            
        except Exception as e:
            logger.error(f"OCR failed on top region: {e}")
            return None
    
    def _expand_modal_boundaries(
        self, 
        image: np.ndarray, 
        header_bbox: Tuple[int, int, int, int]
    ) -> Tuple[int, int, int, int]:
        """
        Expand from header to find full modal boundaries
        
        Strategy:
        - Top: Use header top edge (with small margin)
        - Bottom: Scan downward for footer or large gap
        - Left/Right: Find white rectangle edges
        
        Returns:
            (x1, y1, x2, y2) crop bounds
        """
        height, width = image.shape[:2]
        hx1, hy1, hx2, hy2 = header_bbox
        
        # Top boundary: Header top minus small margin
        top_margin = int(height * 0.02)  # 2% margin
        y1 = max(0, hy1 - top_margin)
        
        # Bottom boundary: Scan downward
        y2 = self._find_bottom_boundary(image, hy2)
        
        # Left/Right boundaries: Find modal edges
        x1, x2 = self._find_horizontal_boundaries(image, y1, y2)
        
        # Add padding
        h_pad = int(width * self.horizontal_padding_ratio)
        v_pad = int(height * self.vertical_padding_ratio)
        
        x1 = max(0, x1 - h_pad)
        y1 = max(0, y1 - v_pad)
        x2 = min(width, x2 + h_pad)
        y2 = min(height, y2 + v_pad)
        
        return (x1, y1, x2, y2)
    
    def _find_bottom_boundary(self, image: np.ndarray, start_y: int) -> int:
        """
        Find bottom edge of modal by scanning downward
        
        Strategy:
        1. Scan from start_y downward
        2. Look for footer keywords using OCR
        3. Stop at large whitespace gap
        4. Use heuristic max height as fallback
        """
        height, width = image.shape[:2]
        max_y = int(height * self.max_modal_height_ratio)
        
        # Search region from start_y to max_y
        search_region = image[start_y:max_y, :].copy()
        
        # Run OCR to find footer
        if self.ocr_engine is not None:
            try:
                result = self.ocr_engine.ocr(search_region, cls=False)
                
                if result and result[0]:
                    for line in result[0]:
                        box = line[0]
                        text = line[1][0].strip().lower()
                        
                        # Check for footer keywords
                        if any(keyword in text for keyword in self.footer_keywords):
                            # Found footer, stop here
                            footer_y = int(min(p[1] for p in box))
                            absolute_y = start_y + footer_y
                            logger.info(f"Footer found at Y={absolute_y}: '{text}'")
                            return absolute_y
            except Exception as e:
                logger.warning(f"Footer detection failed: {e}")
        
        # Fallback: Use heuristic (modal should end around 70-80% of image)
        fallback_y = int(height * 0.75)
        logger.info(f"Using fallback bottom boundary: Y={fallback_y}")
        return fallback_y
    
    def _find_horizontal_boundaries(
        self, 
        image: np.ndarray, 
        y1: int, 
        y2: int
    ) -> Tuple[int, int]:
        """
        Find left and right edges of modal
        
        Strategy:
        - Sample middle rows of modal region
        - Find consistent white/light background
        - Detect edges where background changes
        """
        height, width = image.shape[:2]
        
        # Sample middle region for edge detection
        mid_y = (y1 + y2) // 2
        sample_height = min(100, (y2 - y1) // 4)
        sample_region = image[mid_y:mid_y + sample_height, :]
        
        # Convert to grayscale
        if len(sample_region.shape) == 3:
            gray = cv2.cvtColor(sample_region, cv2.COLOR_BGR2GRAY)
        else:
            gray = sample_region
        
        # Calculate mean intensity per column
        col_means = np.mean(gray, axis=0)
        
        # Threshold for "bright" columns (modal background is white/light)
        brightness_threshold = np.percentile(col_means, 25)  # Bottom 25% is dark
        
        # Find leftmost bright column
        bright_cols = np.where(col_means > brightness_threshold)[0]
        
        if len(bright_cols) == 0:
            # Fallback: Use center region
            logger.warning("Could not detect modal edges, using center region")
            margin = int(width * 0.1)
            return (margin, width - margin)
        
        x1 = int(bright_cols[0])
        x2 = int(bright_cols[-1])
        
        # Ensure minimum width
        modal_width = x2 - x1
        if modal_width < width * 0.40:  # Modal should be at least 40% of image width
            logger.warning(f"Detected width too narrow ({modal_width}px), expanding")
            center_x = (x1 + x2) // 2
            target_width = int(width * 0.60)
            x1 = max(0, center_x - target_width // 2)
            x2 = min(width, center_x + target_width // 2)
        
        return (x1, x2)
    
    def _detect_modal_heuristic(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Fallback heuristic detection when header OCR fails
        
        Assumes modal is:
        - Centered horizontally
        - Takes up 60-80% of width
        - Takes up 50-75% of height
        - Starts around 10-15% from top
        """
        height, width = image.shape[:2]
        
        logger.info("Using heuristic modal detection")
        
        # Heuristic bounds
        x1 = int(width * 0.10)   # 10% from left
        x2 = int(width * 0.90)   # 10% from right
        y1 = int(height * 0.12)  # 12% from top
        y2 = int(height * 0.75)  # 75% from top
        
        return (x1, y1, x2, y2)
    
    def _normalize_modal(self, modal_image: np.ndarray) -> np.ndarray:
        """
        Normalize cropped modal to fixed dimensions
        
        Steps:
        1. Resize to target width (1280px)
        2. Preserve aspect ratio
        3. Apply very light sharpening
        """
        height, width = modal_image.shape[:2]
        
        # Resize to target width
        if width != self.target_width:
            aspect_ratio = height / width
            target_height = int(self.target_width * aspect_ratio)
            
            resized = cv2.resize(
                modal_image, 
                (self.target_width, target_height),
                interpolation=cv2.INTER_LINEAR
            )
        else:
            resized = modal_image
        
        # Apply very light sharpening (optional)
        kernel = np.array([
            [0, -0.5, 0],
            [-0.5, 3, -0.5],
            [0, -0.5, 0]
        ])
        sharpened = cv2.filter2D(resized, -1, kernel)
        
        # Blend with original for subtle effect
        normalized = cv2.addWeighted(resized, 0.7, sharpened, 0.3, 0)
        
        return normalized


def detect_and_crop_modal(
    image: np.ndarray,
    ocr_engine: Optional[PaddleOCR] = None
) -> Tuple[np.ndarray, Dict]:
    """
    Convenience function for modal detection and cropping
    
    Args:
        image: Input screenshot (BGR format)
        ocr_engine: Reuse existing PaddleOCR instance (recommended)
    
    Returns:
        (cropped_modal, debug_info)
        
    Raises:
        ValueError: If modal cannot be detected
    """
    detector = ModalDetector(ocr_engine=ocr_engine)
    return detector.detect_and_crop_modal(image)
