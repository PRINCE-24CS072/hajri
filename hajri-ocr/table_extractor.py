"""
Table extraction using PaddleOCR with coordinate-based parsing and fuzzy matching
"""
import re
import json
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
import numpy as np
import cv2
from PIL import Image as PILImage
from paddleocr import PaddleOCR
from models import AttendanceEntry
import logging

logger = logging.getLogger(__name__)


class TableExtractor:
    """Extracts attendance data from table images using hybrid approach"""
    
    def __init__(self, use_gpu: bool = False, config: Optional[Dict] = None):
        """Initialize OCR configuration (lazy loading of OCR engine)"""
        self.config = {
            'use_angle_cls': False,
            'lang': 'en',
            'use_gpu': use_gpu,
            'show_log': False,
            'det_limit_side_len': 1280,
            'det_db_thresh': 0.2,
            'det_db_box_thresh': 0.3,
            'rec_batch_num': 6,
            'drop_score': 0.2,
            'cpu_threads': 4,
            'enable_mkldnn': False
        }
        
        if config:
            self.config.update(config)
        
        self.paddle_ocr = None  # Lazy initialization
        
        # Load course configuration for fuzzy matching
        self.course_db = self._load_course_config()
        self.valid_course_codes = list(self.course_db.keys())
        logger.info(f"Loaded {len(self.valid_course_codes)} course codes for validation")
    
    def _load_course_config(self) -> Dict:
        """Load course configuration from JSON file"""
        config_path = Path(__file__).parent / "course_config.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('courses', {})
        except FileNotFoundError:
            logger.warning(f"Course config not found at {config_path}, using empty database")
            return {}
        except Exception as e:
            logger.error(f"Error loading course config: {e}")
            return {}
    
    def _fuzzy_match_course_code(self, ocr_code: str) -> Tuple[Optional[str], float]:
        """
        Find best matching course code using fuzzy string matching.
        Returns: (matched_code, confidence_score)
        """
        if not ocr_code or not self.valid_course_codes:
            return None, 0.0
        
        ocr_clean = ocr_code.upper().strip()
        
        # Exact match first
        if ocr_clean in self.valid_course_codes:
            return ocr_clean, 1.0
        
        # Fuzzy match using sequence similarity
        best_match = None
        best_score = 0.0
        
        for valid_code in self.valid_course_codes:
            # Calculate similarity ratio
            ratio = SequenceMatcher(None, ocr_clean, valid_code).ratio()
            
            if ratio > best_score:
                best_score = ratio
                best_match = valid_code
        
        # Only return if confidence is high enough
        threshold = 0.75  # 75% similarity required
        if best_score >= threshold:
            if best_match != ocr_clean:
                print(f"    🔍 Fuzzy matched '{ocr_clean}' → '{best_match}' (confidence: {best_score:.1%})")
            return best_match, best_score
        
        return None, best_score
    
    def _sanitize_course_code(self, text: str) -> str:
        """Sanitize OCR output to fix common errors in course codes"""
        text = text.upper().strip()
        
        # Fix common OCR mistakes
        # In course codes: I→1, O→0 in digit positions, l→1
        sanitized = text
        
        # Pattern: XXXX### where X=letter, #=digit
        # Fix digits that look like letters
        sanitized = sanitized.replace('O', '0')  # O to zero
        sanitized = sanitized.replace('o', '0')
        sanitized = sanitized.replace('l', '1')  # lowercase L to 1
        
        # Remove common noise characters
        sanitized = sanitized.replace(' ', '').replace('/', '').replace('-', '')
        
        return sanitized
    
    def _validate_and_fix_course_code(self, text: str) -> Optional[str]:
        """Extract and validate course code with intelligent fuzzy matching"""
        # Expected format: 3-4 letters + 3 digits (CEUC201, ITUE204, ITUC202)
        
        text_upper = text.upper().strip()
        
        # Try exact pattern first
        match = re.search(r'([A-Z]{3,4})(\d{3})', text_upper)
        if match:
            prefix = match.group(1)
            digits = match.group(2)
            candidate = prefix + digits
            
            # Use fuzzy matching against known course codes
            matched_code, confidence = self._fuzzy_match_course_code(candidate)
            if matched_code:
                return matched_code
        
        # Try with sanitization
        sanitized = self._sanitize_course_code(text)
        match = re.search(r'([A-Z]{3,4})(\d{3})', sanitized)
        if match:
            prefix = match.group(1)
            digits = match.group(2)
            candidate = prefix + digits
            
            # Use fuzzy matching
            matched_code, confidence = self._fuzzy_match_course_code(candidate)
            if matched_code:
                return matched_code
        
        # Last resort: try partial matches
        # Extract any 6-7 character alphanumeric sequence
        partial = re.search(r'([A-Z]{2,4}\d{2,3})', sanitized)
        if partial:
            candidate = partial.group(1)
            # Pad to 7 chars if needed for fuzzy match
            if len(candidate) == 6:
                # Try different padding strategies
                candidates = [
                    candidate[0] + candidate,  # Duplicate first letter
                    'I' + candidate if candidate[0] in 'TUCESM' else candidate,
                    'C' + candidate if candidate[0] in 'EUV' else candidate
                ]
                for cand in candidates:
                    matched_code, confidence = self._fuzzy_match_course_code(cand)
                    if matched_code:
                        return matched_code
        
        return None
    
    def _get_ocr(self):
        """Lazy initialize PaddleOCR on first use"""
        if self.paddle_ocr is None:
            print("🚀 Initializing PaddleOCR engine...")
            self.paddle_ocr = PaddleOCR(**self.config)
            print("✓ PaddleOCR ready")
        return self.paddle_ocr
    
    def extract_table_data(self, image: np.ndarray) -> List[AttendanceEntry]:
        """Extract attendance entries directly from image"""
        # Skip img2table - coordinate-based extraction works better for this dashboard
        logger.info("Using coordinate-based extraction with enhanced preprocessing")
        return self._coordinate_based_extraction(image)
    
    def _parse_structured_table(self, table_content: List[List]) -> List[AttendanceEntry]:
        """Parse img2table output into AttendanceEntry objects"""
        entries = []
        
        # Skip header row
        data_rows = table_content[1:] if len(table_content) > 1 else table_content
        
        for row in data_rows:
            try:
                # Convert None to empty string
                row_clean = [str(cell) if cell is not None else "" for cell in row]
                row_text = " ".join(row_clean)
                
                # Extract course code
                course_code_match = re.search(r'\b([A-Z]{3,4}\d{2,3})\b', row_text)
                if not course_code_match:
                    continue
                course_code = course_code_match.group(1)
                
                # Extract attendance numbers
                attendance_match = re.search(r'(\d+)\s*/\s*(\d+)', row_text.replace('o', '0').replace('O', '0'))
                if not attendance_match:
                    continue
                present = int(attendance_match.group(1))
                total = int(attendance_match.group(2))
                
                # Extract class type
                class_type = "LAB" if "LAB" in row_text.upper() else "LECT"
                
                # Find long course name
                course_name = None
                for cell in row_clean:
                    if len(cell) > 15 and cell.isupper():
                        course_name = cell
                        break
                
                if not course_name:
                    # Look for abbreviated name after slash
                    abbr_match = re.search(r'/\s*([A-Z]{2,10})', row_text)
                    course_name = abbr_match.group(1) if abbr_match else "UNKNOWN"
                
                percentage = round((present / total * 100), 1) if total > 0 else 0.0
                
                entries.append(AttendanceEntry(
                    course_code=course_code,
                    course_name=course_name,
                    class_type=class_type,
                    present=present,
                    total=total,
                    percentage=percentage,
                    confidence=0.85
                ))
                
                logger.info(f"✓ Parsed: {course_code} | {class_type} | {present}/{total} | {course_name}")
                
            except Exception as e:
                logger.warning(f"Failed to parse row: {e}")
                continue
        
        return entries
    
    def _coordinate_based_extraction(self, image: np.ndarray) -> List[AttendanceEntry]:
        """Fallback: Extract using coordinate analysis"""
        try:
            # Debug: Save preprocessed image for analysis
            cv2.imwrite('debug_preprocessed.png', image)
            print(f"💾 Saved debug_preprocessed.png (shape: {image.shape})")
            print(f"📊 Image stats: min={image.min()}, max={image.max()}, mean={image.mean():.1f}")
            
            result = self._get_ocr().ocr(image, cls=True)
            
            if not result or not result[0]:
                return []
            
            # Build text boxes with coordinates
            text_boxes = []
            for line in result[0]:
                box = line[0]
                text = line[1][0].strip()
                confidence = line[1][1]
                
                y_mid = (box[0][1] + box[2][1]) / 2
                x_mid = (box[0][0] + box[1][0]) / 2
                
                text_boxes.append({
                    'text': text,
                    'conf': confidence,
                    'y': y_mid,
                    'x': x_mid
                })
            
            logger.info(f"OCR detected {len(text_boxes)} text boxes")
            
            # Log first 10 text boxes for debugging
            for i, box in enumerate(text_boxes[:10]):
                logger.debug(f"Box {i}: '{box['text']}' at ({box['x']:.0f}, {box['y']:.0f})")
            
            logger.info(f"OCR detected {len(text_boxes)} text boxes")
            print(f"🔍 OCR detected {len(text_boxes)} text boxes")
            
            # Log first 10 text boxes for debugging
            for i, box in enumerate(text_boxes[:10]):
                logger.info(f"Box {i}: '{box['text']}' at ({box['x']:.0f}, {box['y']:.0f})")
                print(f"📦 Box {i}: '{box['text']}' at ({box['x']:.0f}, {box['y']:.0f})")
            
            # Group into rows (tighter tolerance for better separation)
            rows_dict = {}
            avg_height = 30  # Approximate
            tolerance = 12  # Reduced from 25 for better row separation
            
            for box in text_boxes:
                # Skip headers
                if any(word in box['text'].upper() for word in ['COURSE', 'CLASS', 'TYPE', 'PRESENT', 'TOTAL']):
                    continue
                if len(box['text']) < 2:
                    continue
                
                # Find or create row
                matched_y = None
                for y in rows_dict.keys():
                    if abs(box['y'] - y) <= tolerance:
                        matched_y = y
                        break
                
                if matched_y is None:
                    matched_y = box['y']
                    rows_dict[matched_y] = []
                
                rows_dict[matched_y].append(box)
            
            # Parse each row
            entries = []
            logger.info(f"Found {len(rows_dict)} potential rows to parse")
            print(f"📊 Found {len(rows_dict)} potential rows to parse")
            
            for y in sorted(rows_dict.keys()):
                row_boxes = sorted(rows_dict[y], key=lambda b: b['x'])
                row_text = " | ".join([b['text'] for b in row_boxes])
                logger.info(f"Parsing row at y={y}: {row_text}")
                print(f"🔄 Parsing row: {row_text}")
                
                entry = self._parse_coordinate_row(row_boxes)
                if entry:
                    entries.append(entry)
                    print(f"✅ Row ACCEPTED")
                else:
                    logger.info(f"Row rejected (no course code or attendance found)")
                    print(f"❌ Row REJECTED")
            
            logger.info(f"Successfully extracted {len(entries)} attendance entries")
            print(f"🎯 Final result: {len(entries)} entries extracted")
            return entries
            
        except Exception as e:
            logger.error(f"Coordinate extraction failed: {e}")
            return []
    
    def _parse_coordinate_row(self, boxes: List[dict]) -> Optional[AttendanceEntry]:
        """
        Smart parsing algorithm for attendance table rows.
        Handles: Same course appearing multiple times (LECT + LAB with different attendance)
        Table structure: Course | Class Type | Present/Total | Percentage | Course Code | Course Name
        """
        if len(boxes) < 3:
            print(f"  ⚠️ Row has only {len(boxes)} cells, need at least 3")
            return None
        
        # Sort boxes left-to-right for column identification
        sorted_boxes = sorted(boxes, key=lambda b: b['x'])
        all_text = " ".join([b['text'] for b in boxes])
        print(f"  📝 Row text: {all_text}")
        
        # === STEP 1: Extract Course Code (most reliable identifier) ===
        # Strategy: Look in right half (Course Code column is on right side)
        mid_point = len(sorted_boxes) // 2
        right_boxes = sorted_boxes[mid_point:]
        
        course_code = None
        # First pass: Try to extract from right-side boxes (Course Code column)
        for box in right_boxes:
            validated = self._validate_and_fix_course_code(box['text'])
            if validated:
                course_code = validated
                print(f"  ✓ Course code (right): {course_code}")
                break
        
        # Second pass: Try left-side boxes if needed
        if not course_code:
            for box in sorted_boxes[:mid_point]:
                validated = self._validate_and_fix_course_code(box['text'])
                if validated:
                    course_code = validated
                    print(f"  ✓ Course code (left): {course_code}")
                    break
        
        # Final fallback: search all text
        if not course_code:
            validated = self._validate_and_fix_course_code(all_text)
            if validated:
                course_code = validated
                print(f"  ✓ Course code (fallback): {course_code}")
        
        if not course_code:
            print(f"  ❌ No valid course code found in: {all_text}")
            return None
        
        # === STEP 2: Extract Class Type (LECT or LAB) - Critical for duplicates! ===
        class_type = "LECT"  # Default
        for box in sorted_boxes:
            text_upper = box['text'].upper()
            if "LAB" in text_upper:
                class_type = "LAB"
                print(f"  ✓ Class type: LAB")
                break
            elif "LECT" in text_upper:
                class_type = "LECT"
                print(f"  ✓ Class type: LECT")
                break
        
        # === STEP 3: Extract Attendance (Present/Total) ===
        # Clean OCR errors: o→0, O→0, l→1, I→1, S→5, s→5
        clean_text = all_text.replace('o', '0').replace('O', '0').replace('l', '1').replace('I', '1')
        clean_text = clean_text.replace('S', '5').replace('s', '5').replace('B', '8')
        
        # Find attendance pattern
        attendance_match = re.search(r'(\d+)\s*/\s*(\d+)', clean_text)
        
        if not attendance_match:
            return None
        
        present = int(attendance_match.group(1))
        total = int(attendance_match.group(2))
        
        # === STEP 4: Extract Course Name ===
        # First try: Get from course database (most reliable)
        if course_code in self.course_db:
            course_name = self.course_db[course_code]['name']
            print(f"  ✓ Course name (database): {course_name}")
        else:
            # Fallback: Look for long uppercase text (likely full course name)
            course_name = None
            for box in right_boxes:  # Prioritize right side
                if len(box['text']) > 15:  # Long text = full name
                    # Clean up the course name
                    cleaned_name = box['text'].strip().upper()
                    # Fix common OCR mixed-case errors
                    cleaned_name = cleaned_name.replace('i', 'I').replace('o', 'O')
                    course_name = cleaned_name
                    print(f"  ✓ Course name (OCR): {course_name}")
                    break
            
            # Last resort: use abbreviation from "Course" column
            if not course_name:
                abbr_match = re.search(r'/\s*([A-Z]{2,10})', all_text.upper())
                course_name = abbr_match.group(1) if abbr_match else "UNKNOWN"
                print(f"  ✓ Course name (abbr): {course_name}")
        
        percentage = round((present / total * 100), 1) if total > 0 else 0.0
        
        logger.info(f"✓ Extracted: {course_code} | {class_type} | {present}/{total} ({percentage}%) | {course_name}")

        
        return AttendanceEntry(
            course_code=course_code,
            course_name=course_name,
            class_type=class_type,
            present=present,
            total=total,
            percentage=percentage,
            confidence=0.80
        )
    
    def update_config(self, config: Dict):
        """Update OCR configuration"""
        self.config.update(config)
        self.paddle_ocr = None  # Reset for lazy reload
