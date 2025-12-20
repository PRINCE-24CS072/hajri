"""
Image preprocessing for better OCR accuracy
Includes modal detection and cropping for zoomed-out screenshots
"""
import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Optional, Dict
import io
import logging

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Handles image preprocessing for OCR
    
    Pipeline:
    1. Load image
    2. Initial resize (max 1920px width)
    3. Detect and crop modal (removes background UI)
    4. Normalize cropped modal
    5. Light enhancement for OCR
    """
    
    def __init__(self, enable_modal_detection: bool = True):
        """
        Initialize preprocessor
        
        Args:
            enable_modal_detection: If True, automatically detect and crop modal
        """
        self.enable_modal_detection = enable_modal_detection
        self.modal_detector = None  # Lazy initialization
    
    @staticmethod
    def load_image(image_bytes: bytes) -> np.ndarray:
        """Load image from bytes"""
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise ValueError("Failed to decode image")
        
        return image
    
    @staticmethod
    def resize_if_needed(image: np.ndarray, max_width: int = 1920) -> np.ndarray:
        """Resize image if too large (preserves aspect ratio)"""
        height, width = image.shape[:2]
        
        if width <= max_width:
            return image
        
        ratio = max_width / width
        new_width = max_width
        new_height = int(height * ratio)
        
        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """Enhance image contrast using CLAHE"""
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Apply CLAHE to L channel - more aggressive for grey lines
        clahe = cv2.createCLAHE(clipLimit=4.5, tileGridSize=(8, 8))
        l = clahe.apply(l)
        
        # Merge channels
        enhanced = cv2.merge([l, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    
    @staticmethod
    def enhance_grey_lines(image: np.ndarray) -> np.ndarray:
        """Strengthen grey table lines for better detection"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect edges (grey lines become more visible)
        edges = cv2.Canny(gray, 30, 100)
        
        # Dilate edges slightly to make lines thicker
        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        # Merge edges back with original
        # This makes grey lines darker
        gray_enhanced = cv2.subtract(gray, edges)
        
        # Convert back to BGR
        return cv2.cvtColor(gray_enhanced, cv2.COLOR_GRAY2BGR)
    
    @staticmethod
    def enhance_table_structure(image: np.ndarray) -> np.ndarray:
        """Detect and enhance table structure (lines and borders)"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Morphological operations to detect horizontal and vertical lines
        # Horizontal lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        
        # Vertical lines
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        vertical_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
        
        # Combine lines
        table_structure = cv2.addWeighted(horizontal_lines, 0.5, vertical_lines, 0.5, 0)
        
        # Threshold to get binary lines
        _, table_binary = cv2.threshold(table_structure, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Invert so lines are black on white
        table_binary = cv2.bitwise_not(table_binary)
        
        # Merge with original image
        # Make detected lines darker in the original
        gray_enhanced = np.where(table_binary < 128, gray * 0.5, gray).astype(np.uint8)
        
        return cv2.cvtColor(gray_enhanced, cv2.COLOR_GRAY2BGR)
    
    @staticmethod
    def denoise(image: np.ndarray) -> np.ndarray:
        """Remove noise from image"""
        return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
    
    @staticmethod
    def sharpen(image: np.ndarray) -> np.ndarray:
        """Sharpen image for better text clarity"""
        # Stronger sharpening kernel
        kernel = np.array([[-1, -1, -1],
                          [-1, 11, -1],
                          [-1, -1, -1]])
        sharpened = cv2.filter2D(image, -1, kernel)
        
        # Apply unsharp mask for additional clarity
        gaussian = cv2.GaussianBlur(sharpened, (0, 0), 2.0)
        return cv2.addWeighted(sharpened, 1.5, gaussian, -0.5, 0)
    
    @staticmethod
    def binarize(image: np.ndarray) -> np.ndarray:
        """Convert to binary (black and white) for better OCR"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Adaptive thresholding works better for tables
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        return binary
    
    def preprocess_for_table(self, image_bytes: bytes) -> Tuple[np.ndarray, np.ndarray]:
        """
        Full preprocessing pipeline optimized for table extraction
        Returns: (original_color, preprocessed_for_ocr)
        """
        # Load image
        original = self.load_image(image_bytes)
        
        # Resize if too large
        resized = self.resize_if_needed(original)
        
        # STEP 1: Enhance table structure (make grey lines darker)
        table_enhanced = self.enhance_table_structure(resized)
        
        # STEP 2: Enhance overall contrast
        contrast_enhanced = self.enhance_contrast(table_enhanced)
        
        # STEP 3: Additional grey line enhancement
        grey_enhanced = self.enhance_grey_lines(contrast_enhanced)
        
        # STEP 4: Sharpen for text clarity
        sharpened = self.sharpen(grey_enhanced)
        
        return resized, sharpened
    
    def preprocess_simple(self, image_bytes: bytes) -> np.ndarray:
        """Simple preprocessing - just resize and enhance for speed"""
        original = self.load_image(image_bytes)
        resized = self.resize_if_needed(original)
        
        # Quick grey line enhancement
        table_enhanced = self.enhance_table_structure(resized)
        
        # Contrast boost
        enhanced = self.enhance_contrast(table_enhanced)
        
        return enhanced
    
    def preprocess_clean(self, image_bytes: bytes) -> np.ndarray:
        """Clean preprocessing optimized for OCR accuracy (no aggressive processing)"""
        # Load and resize
        original = self.load_image(image_bytes)
        height, width = original.shape[:2]
        
        # Upscale if too small (OCR works better on larger images)
        if width < 1920:
            scale = 1920 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            resized = cv2.resize(original, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        else:
            resized = original
        
        # Convert to grayscale
        if len(resized.shape) == 3:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        else:
            gray = resized
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # Adaptive threshold for crisp black/white text
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, blockSize=21, C=10
        )
        
        # Convert back to BGR for PaddleOCR
        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        
        return result
    
    def preprocess_screenshot(
        self, 
        image_bytes: bytes, 
        ocr_engine=None,
        detect_modal: Optional[bool] = None
    ) -> Tuple[np.ndarray, Dict]:
        """
        Full preprocessing pipeline with modal detection
        
        Pipeline:
        1. Load and initial resize (max 1920px)
        2. Detect and crop modal (if enabled)
        3. Light enhancement for OCR
        
        Args:
            image_bytes: Input image bytes
            ocr_engine: Reuse PaddleOCR instance for modal detection
            detect_modal: Override modal detection setting (default: use instance setting)
        
        Returns:
            (preprocessed_image, debug_info)
        """
        # Load image
        original = self.load_image(image_bytes)
        height, width = original.shape[:2]
        
        debug_info = {
            'original_size': (width, height),
            'modal_detected': False,
            'modal_bounds': None,
        }
        
        # Initial resize (max 1920px width for modal detection)
        if width > 1920:
            resized = self.resize_if_needed(original, max_width=1920)
            logger.info(f"Resized from {width}x{height} to {resized.shape[1]}x{resized.shape[0]}")
        else:
            resized = original
        
        # Determine if we should detect modal
        should_detect = detect_modal if detect_modal is not None else self.enable_modal_detection
        
        # Modal detection and cropping
        if should_detect:
            try:
                from modal_detector import ModalDetector
                
                # Lazy initialize detector
                if self.modal_detector is None:
                    self.modal_detector = ModalDetector(ocr_engine=ocr_engine)
                elif ocr_engine is not None:
                    # Update OCR engine if provided
                    self.modal_detector.ocr_engine = ocr_engine
                
                # Detect and crop modal
                logger.info("Attempting modal detection...")
                cropped, modal_debug = self.modal_detector.detect_and_crop_modal(resized)
                
                debug_info['modal_detected'] = True
                debug_info['modal_bounds'] = modal_debug.get('crop_bounds')
                debug_info['modal_detection_method'] = modal_debug.get('detection_method')
                debug_info['normalized_size'] = modal_debug.get('normalized_size')
                
                logger.info(f"Modal detected and cropped: {cropped.shape[1]}x{cropped.shape[0]}px")
                
                # Use cropped modal for OCR
                to_process = cropped
                
            except Exception as e:
                logger.warning(f"Modal detection failed: {e}. Using full image.")
                debug_info['modal_detection_error'] = str(e)
                to_process = resized
        else:
            logger.info("Modal detection disabled, using full image")
            to_process = resized
        
        # Light enhancement for OCR (minimal processing)
        enhanced = self._light_enhance(to_process)
        
        debug_info['final_size'] = (enhanced.shape[1], enhanced.shape[0])
        
        return enhanced, debug_info
    
    def _light_enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Light enhancement for OCR
        
        Minimal processing to preserve table structure:
        - Very light sharpening
        - No binarization
        - No aggressive morphology
        """
        # Slight sharpening to enhance text edges
        kernel = np.array([
            [0, -0.5, 0],
            [-0.5, 3, -0.5],
            [0, -0.5, 0]
        ])
        sharpened = cv2.filter2D(image, -1, kernel)
        
        # Blend with original for subtle effect
        enhanced = cv2.addWeighted(image, 0.7, sharpened, 0.3, 0)
        
        return enhanced
