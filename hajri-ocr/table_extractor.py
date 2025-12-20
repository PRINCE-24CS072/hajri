"""
Anchor-Based Table Extraction using PaddleOCR
Deterministic, rule-based, CPU-only OCR extraction for attendance data
NO ML training, NO row clustering, ONLY geometry-based anchor matching
"""
import re
from typing import List, Dict, Optional, Tuple
import numpy as np
import cv2
from paddleocr import PaddleOCR
from models import AttendanceEntry
import logging

logger = logging.getLogger(__name__)


class TableExtractor:
    """
    Anchor-based attendance table extractor
    
    Core Principle: Rows do NOT exist. Anchors exist.
    A logical row = (course_code + class_type)
    All fields attach to anchors via geometry, not OCR rows.
    """
    
    def __init__(self, use_gpu: bool = False, config: Optional[Dict] = None, ocr_engine: Optional[PaddleOCR] = None):
        """Initialize OCR configuration (lazy loading of OCR engine or reuse provided one)"""
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
        
        self.paddle_ocr = ocr_engine  # Use provided engine or lazy initialize later
        
        # Column zones (relative to image width)
        self.COURSE_CODE_ZONE = (0.00, 0.35)
        self.CLASS_TYPE_ZONE = (0.35, 0.50)
        self.ATTENDANCE_ZONE = (0.50, 0.75)
        self.PERCENTAGE_ZONE = (0.75, 1.00)
        
        # Matching tolerance (pixels)
        self.y_tolerance = 20.0  # Vertical distance tolerance for field matching
        
        # Right table split threshold
        self.region_split_threshold = 0.52  # % of image width
        
        # Debug storage
        self.debug_info = {}
        self.debug_mode = False
        
        logger.info("Anchor-based TableExtractor initialized - deterministic geometry matching")
    
    # ==================== CORE ANCHOR-BASED EXTRACTION ====================
    
    def _tokenize_ocr_lines(self, ocr_lines: List) -> Tuple[List[Dict], float]:
        """
        Convert PaddleOCR raw lines into token dicts with geometric info.
        Returns: (tokens, image_width)
        
        Each token:
        {
            'text': str,
            'conf': float,
            'x_center': float,
            'y_center': float,
            'box': [[x,y], ...]
        }
        """
        tokens = []
        max_x = 0.0
        
        for line in ocr_lines:
            box = line[0]
            text = line[1][0].strip()
            confidence = line[1][1]

            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]
            x_center = sum(x_coords) / 4.0
            y_center = sum(y_coords) / 4.0
            max_x = max(max_x, max(x_coords))

            tokens.append({
                'text': text,
                'conf': confidence,
                'x_center': x_center,
                'y_center': y_center,
                'box': box
            })

        return tokens, max_x
    
    def _split_left_right(self, tokens: List[Dict], image_width: float) -> Tuple[List[Dict], List[Dict]]:
        """
        Split tokens into left (attendance) and right (dictionary) tables.
        Uses configurable region_split_threshold.
        """
        threshold = image_width * self.region_split_threshold
        
        left = [t for t in tokens if t['x_center'] < threshold]
        right = [t for t in tokens if t['x_center'] >= threshold]
        
        # Adaptive fallback if one side empty
        if (not left or not right) and tokens:
            xs = sorted(t['x_center'] for t in tokens)
            threshold = xs[len(xs) // 2]
            left = [t for t in tokens if t['x_center'] < threshold]
            right = [t for t in tokens if t['x_center'] >= threshold]
        
        if self.debug_mode:
            self.debug_info['split_threshold'] = threshold
            self.debug_info['image_width'] = image_width
        
        return left, right
    
    def _get_x_ratio(self, x_center: float, image_width: float) -> float:
        """Get normalized x position (0.0 to 1.0)"""
        return x_center / image_width if image_width > 0 else 0.0
    
    def _in_zone(self, x_ratio: float, zone: Tuple[float, float]) -> bool:
        """Check if x_ratio is within zone bounds"""
        return zone[0] <= x_ratio < zone[1]
    
    def _detect_anchors(self, left_tokens: List[Dict], image_width: float) -> List[Dict]:
        """
        Step 1: Detect anchors (course_code + class_type pairs)
        
        An anchor is detected when:
        - Token matches [A-Z]{3,4}\\d{3} pattern
        - AND nearby token (same horizontal band) is LECT or LAB
        
        Returns list of anchors:
        [{
            'course_code': str,
            'class_type': str,
            'x_center': float,
            'y_center': float
        }]
        """
        anchors = []
        
        # Find all course code candidates
        course_code_pattern = re.compile(r'[A-Z]{3,4}\d{3}')
        
        for token in left_tokens:
            # Match course code
            match = course_code_pattern.search(token['text'].upper())
            if not match:
                continue
            
            course_code = match.group(0)
            x_ratio = self._get_x_ratio(token['x_center'], image_width)
            
            # Must be in course code zone
            if not self._in_zone(x_ratio, self.COURSE_CODE_ZONE):
                continue
            
            # Find nearby class type (LECT or LAB)
            class_type = None
            for other in left_tokens:
                if other is token:
                    continue
                
                # Check Y proximity (same horizontal band)
                if abs(other['y_center'] - token['y_center']) > self.y_tolerance:
                    continue
                
                # Check if token contains LECT or LAB
                text_upper = other['text'].upper()
                if 'LECT' in text_upper:
                    class_type = 'LECT'
                    break
                elif 'LAB' in text_upper:
                    class_type = 'LAB'
                    break
            
            if class_type:
                anchors.append({
                    'course_code': self._normalize_course_code(course_code),
                    'class_type': class_type,
                    'x_center': token['x_center'],
                    'y_center': token['y_center']
                })
                logger.info(f"Anchor detected: {course_code} {class_type} at Y={token['y_center']:.1f}")
        
        return anchors
    
    def _detect_attendance_fields(self, left_tokens: List[Dict], image_width: float) -> List[Dict]:
        """
        Step 2: Detect attendance fields (X/Y pattern)
        
        Returns list of fields:
        [{
            'present': int,
            'total': int,
            'x_center': float,
            'y_center': float
        }]
        """
        attendance_pattern = re.compile(r'(\d+)\s*/\s*(\d+)')
        fields = []
        
        for token in left_tokens:
            # Clean OCR errors (O->0, I/L->1)
            clean_text = token['text'].upper().replace('O', '0').replace('L', '1').replace('I', '1')
            
            match = attendance_pattern.search(clean_text)
            if not match:
                continue
            
            present = int(match.group(1))
            total = int(match.group(2))
            
            # Sanity check
            if present > 100 or total > 100:
                continue
            
            x_ratio = self._get_x_ratio(token['x_center'], image_width)
            
            # Must be in attendance zone
            if not self._in_zone(x_ratio, self.ATTENDANCE_ZONE):
                continue
            
            fields.append({
                'present': present,
                'total': total,
                'x_center': token['x_center'],
                'y_center': token['y_center']
            })
        
        return fields
    
    def _detect_percentage_fields(self, left_tokens: List[Dict], image_width: float) -> List[Dict]:
        """
        Step 3: Detect percentage fields (X% or X.Y%)
        
        Returns list of fields:
        [{
            'percentage': float,
            'x_center': float,
            'y_center': float
        }]
        """
        percentage_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*%')
        fields = []
        
        for token in left_tokens:
            match = percentage_pattern.search(token['text'])
            if not match:
                continue
            
            percentage = float(match.group(1))
            
            # Sanity check
            if percentage > 100:
                continue
            
            x_ratio = self._get_x_ratio(token['x_center'], image_width)
            
            # Must be in percentage zone
            if not self._in_zone(x_ratio, self.PERCENTAGE_ZONE):
                continue
            
            fields.append({
                'percentage': percentage,
                'x_center': token['x_center'],
                'y_center': token['y_center']
            })
        
        return fields
    
    def _match_fields_to_anchors(
        self, 
        anchors: List[Dict], 
        attendance_fields: List[Dict], 
        percentage_fields: List[Dict]
    ) -> List[Dict]:
        """
        Step 4: Match fields to anchors using geometry
        
        For each anchor:
        - Find closest attendance field (in attendance zone, min Y distance)
        - Find closest percentage field (in percentage zone, min Y distance)
        
        Returns entries with attached fields (or None if not found)
        """
        entries = []
        
        for anchor in anchors:
            entry = {
                'course_code': anchor['course_code'],
                'class_type': anchor['class_type'],
                'present': None,
                'total': None,
                'percentage': None,
                'y_center': anchor['y_center']
            }
            
            # Find closest attendance field
            best_attendance = None
            best_attendance_dist = float('inf')
            
            for field in attendance_fields:
                y_dist = abs(field['y_center'] - anchor['y_center'])
                if y_dist < self.y_tolerance and y_dist < best_attendance_dist:
                    best_attendance = field
                    best_attendance_dist = y_dist
            
            if best_attendance:
                entry['present'] = best_attendance['present']
                entry['total'] = best_attendance['total']
            
            # Find closest percentage field
            best_percentage = None
            best_percentage_dist = float('inf')
            
            for field in percentage_fields:
                y_dist = abs(field['y_center'] - anchor['y_center'])
                if y_dist < self.y_tolerance and y_dist < best_percentage_dist:
                    best_percentage = field
                    best_percentage_dist = y_dist
            
            if best_percentage:
                entry['percentage'] = best_percentage['percentage']
            
            entries.append(entry)
        
        return entries
    
    def _normalize_course_code(self, raw_code: str) -> str:
        """
        Normalize course code:
        - Uppercase
        - Remove non-alphanumeric
        - Fix OCR confusions (O/D/Q->0, I/L->1)
        - Format: [A-Z]{3-4}[0-9]{3}
        """
        if not raw_code:
            return ""
        
        # Take left of '/' if present
        left = raw_code.split('/')[0]
        cleaned = re.sub(r'[^A-Z0-9]', '', left.upper())
        
        if not cleaned:
            return ""
        
        # Split letters and tail
        match = re.match(r'([A-Z]{2,5})([A-Z0-9]*)', cleaned)
        if not match:
            return cleaned[:7]
        
        letters, tail = match.group(1), match.group(2)
        
        # Fix numeric tail
        tail_fixed = []
        for ch in tail:
            if ch.isdigit():
                tail_fixed.append(ch)
            else:
                # OCR confusion fixes
                mapped = {'O': '0', 'D': '0', 'Q': '0', 'I': '1', 'L': '1'}
                tail_fixed.append(mapped.get(ch, ch))
        
        # Extract digits (expecting 3)
        digits_only = ''.join([c for c in tail_fixed if c.isdigit()])
        if digits_only:
            digit_part = (digits_only + '000')[:3]
        else:
            digit_part = '000'
        
        normalized = (letters[:4] + digit_part).strip()
        return normalized
    
    def _build_course_dictionary(self, right_tokens: List[Dict]) -> Dict[str, str]:
        """
        Step 5: Build course code -> course name dictionary from RIGHT table
        
        Strategy:
        - Cluster tokens by Y proximity (rows)
        - Find course code in each row
        - Find longest text as course name
        - Build mapping
        
        Returns: {course_code: course_name}
        """
        course_dict = {}
        
        # Simple row clustering by Y
        rows = self._cluster_tokens_by_y(right_tokens)
        
        for row in rows:
            # Skip header rows
            header_text = " ".join(t['text'].upper() for t in row)
            if 'COURSE CODE' in header_text or 'COURSE NAME' in header_text:
                continue
            
            # Find course code
            course_code = None
            for token in row:
                match = re.search(r'[A-Z]{3,4}\d{3}', token['text'].upper())
                if match:
                    course_code = self._normalize_course_code(match.group(0))
                    if course_code:
                        break
            
            if not course_code:
                continue
            
            # Find course name (longest text > 8 chars)
            name_candidates = [
                t['text'].strip().upper()
                for t in row
                if len(t['text'].strip()) > 8
            ]
            
            if not name_candidates:
                continue
            
            course_name = max(name_candidates, key=len)
            course_dict[course_code] = course_name
            logger.info(f"Dictionary: {course_code} -> {course_name}")
        
        return course_dict
    
    def _cluster_tokens_by_y(self, tokens: List[Dict], tolerance: float = 20.0) -> List[List[Dict]]:
        """
        Cluster tokens into rows by Y proximity.
        Returns sorted list of rows (each row sorted left-to-right).
        """
        rows_dict: Dict[float, List[Dict]] = {}
        
        for token in tokens:
            matched_y = None
            for y in rows_dict.keys():
                if abs(token['y_center'] - y) <= tolerance:
                    matched_y = y
                    break
            
            if matched_y is None:
                matched_y = token['y_center']
                rows_dict[matched_y] = []
            
            rows_dict[matched_y].append(token)
        
        # Sort rows by Y, and tokens within each row by X
        rows = []
        for y in sorted(rows_dict.keys()):
            row = sorted(rows_dict[y], key=lambda t: t['x_center'])
            rows.append(row)
        
        return rows
    
    def _inject_course_names(self, entries: List[Dict], course_dict: Dict[str, str]) -> List[Dict]:
        """
        Step 6: Inject course names from dictionary
        
        Sets course_name to:
        - Dictionary value if found
        - "UNKNOWN" if not found
        
        Logs warnings for missing codes.
        """
        for entry in entries:
            course_code = entry['course_code']
            
            if course_code in course_dict:
                entry['course_name'] = course_dict[course_code]
            else:
                entry['course_name'] = 'UNKNOWN'
                logger.warning(f"Dictionary miss: {course_code} (row kept as UNKNOWN)")
        
        return entries
    
    def _validate_entries(self, entries: List[Dict]) -> List[Dict]:
        """
        Step 7: Apply validation rules
        
        Rules:
        1. present <= total
        2. percentage ≈ present/total (±3%)
        3. LAB and LECT remain separate
        4. Duplicate anchors merged deterministically
        5. Invalid rows flagged (not dropped)
        
        Computes percentage if missing.
        """
        validated = []
        
        for entry in entries:
            present = entry.get('present', 0)
            total = entry.get('total', 0)
            percentage = entry.get('percentage')
            
            # Compute percentage if missing
            if percentage is None:
                if total > 0:
                    percentage = round((present / total) * 100, 1)
                else:
                    percentage = 0.0
            
            entry['percentage'] = percentage
            
            # Validation checks (log warnings, don't drop)
            if present is None or total is None:
                logger.warning(f"Missing attendance for {entry['course_code']} {entry['class_type']}")
                entry['present'] = 0
                entry['total'] = 0
            
            if present > total and total > 0:
                logger.warning(f"Invalid: present > total for {entry['course_code']} {entry['class_type']}: {present}/{total}")
            
            if total > 0:
                expected_pct = (present / total) * 100
                if abs(percentage - expected_pct) > 3.0:
                    logger.warning(f"Percentage mismatch for {entry['course_code']} {entry['class_type']}: {percentage}% vs expected {expected_pct:.1f}%")
            
            validated.append(entry)
        
        return validated
    
    def _deduplicate_anchors(self, entries: List[Dict]) -> List[Dict]:
        """
        Step 8: Deduplicate entries by anchor key (course_code, class_type)
        
        If duplicates exist, merge deterministically:
        - Choose entry with non-zero total
        - If tie, choose entry with higher Y (later in page)
        """
        anchor_map = {}  # (course_code, class_type) -> entry
        
        for entry in entries:
            key = (entry['course_code'], entry['class_type'])
            
            if key not in anchor_map:
                anchor_map[key] = entry
            else:
                existing = anchor_map[key]
                
                # Prefer non-zero total
                if entry.get('total', 0) > 0 and existing.get('total', 0) == 0:
                    anchor_map[key] = entry
                    logger.info(f"Duplicate resolved: {key} - chose entry with total={entry['total']}")
                elif entry.get('total', 0) == existing.get('total', 0):
                    # Prefer later Y position
                    if entry.get('y_center', 0) > existing.get('y_center', 0):
                        anchor_map[key] = entry
                        logger.info(f"Duplicate resolved: {key} - chose later Y position")
        
        return list(anchor_map.values())
    
    def _build_final_entries(self, entries: List[Dict]) -> List[AttendanceEntry]:
        """
        Step 9: Convert to AttendanceEntry objects and sort
        
        Sort order:
        1. course_code (ascending)
        2. LECT before LAB
        """
        type_order = {'LECT': 0, 'LAB': 1}
        
        sorted_entries = sorted(
            entries, 
            key=lambda x: (x['course_code'], type_order.get(x['class_type'], 2))
        )
        
        final_entries = []
        for entry in sorted_entries:
            try:
                attendance = AttendanceEntry(
                    course_code=entry['course_code'],
                    course_name=entry.get('course_name', 'UNKNOWN'),
                    class_type=entry['class_type'],
                    present=entry.get('present', 0),
                    total=entry.get('total', 0),
                    percentage=entry.get('percentage', 0.0),
                    confidence=0.95  # Anchor-based extraction is highly confident
                )
                final_entries.append(attendance)
            except Exception as e:
                logger.error(f"Failed to create AttendanceEntry: {e} - Entry: {entry}")
        
        return final_entries
    
    # ==================== MAIN EXTRACTION PIPELINE ====================
    
    def _get_ocr(self):
        """Lazy initialize PaddleOCR on first use"""
        if self.paddle_ocr is None:
            print("🚀 Initializing PaddleOCR engine...")
            self.paddle_ocr = PaddleOCR(**self.config)
            print("✓ PaddleOCR ready")
        return self.paddle_ocr
    
    def extract_table_data(self, image: np.ndarray, debug: bool = False) -> List[AttendanceEntry]:
        """
        Main anchor-based extraction pipeline
        
        Steps:
        1. Run OCR → get tokens
        2. Split left (attendance) vs right (dictionary)
        3. Detect anchors (course_code + class_type pairs)
        4. Detect attendance fields (X/Y)
        5. Detect percentage fields (X%)
        6. Match fields to anchors (geometry-based)
        7. Build course dictionary from right table
        8. Inject course names
        9. Validate and deduplicate
        10. Return final entries
        """
        self.debug_mode = debug
        self.debug_info = {}
        
        try:
            # Step 1: Run OCR
            print("\n[*] Step 1: Running OCR...")
            result = self._get_ocr().ocr(image, cls=True)
            
            if not result or not result[0]:
                print("[FAIL] No OCR results")
                return []
            
            # Step 2: Tokenize
            print("📍 Step 2: Tokenizing...")
            tokens, image_width = self._tokenize_ocr_lines(result[0])
            print(f"   Found {len(tokens)} tokens, image width: {image_width:.0f}px")
            
            # Step 3: Split left/right
            print("✂️  Step 3: Splitting left/right tables...")
            left_tokens, right_tokens = self._split_left_right(tokens, image_width)
            print(f"   Left: {len(left_tokens)} tokens, Right: {len(right_tokens)} tokens")
            
            if self.debug_mode:
                self.debug_info['all_tokens'] = tokens
                self.debug_info['left_tokens'] = left_tokens
                self.debug_info['right_tokens'] = right_tokens
            
            # Step 4: Detect anchors
            print("⚓ Step 4: Detecting anchors...")
            anchors = self._detect_anchors(left_tokens, image_width)
            print(f"   Found {len(anchors)} anchors")
            
            if not anchors:
                print("❌ No anchors detected")
                return []
            
            if self.debug_mode:
                self.debug_info['anchors'] = anchors
            
            # Step 5: Detect attendance fields
            print("📊 Step 5: Detecting attendance fields...")
            attendance_fields = self._detect_attendance_fields(left_tokens, image_width)
            print(f"   Found {len(attendance_fields)} attendance fields")
            
            if self.debug_mode:
                self.debug_info['attendance_fields'] = attendance_fields
            
            # Step 6: Detect percentage fields
            print("📈 Step 6: Detecting percentage fields...")
            percentage_fields = self._detect_percentage_fields(left_tokens, image_width)
            print(f"   Found {len(percentage_fields)} percentage fields")
            
            if self.debug_mode:
                self.debug_info['percentage_fields'] = percentage_fields
            
            # Step 7: Match fields to anchors
            print("🔗 Step 7: Matching fields to anchors...")
            entries = self._match_fields_to_anchors(anchors, attendance_fields, percentage_fields)
            print(f"   Created {len(entries)} entries")
            
            # Step 8: Build course dictionary
            print("📚 Step 8: Building course dictionary...")
            course_dict = self._build_course_dictionary(right_tokens)
            print(f"   Dictionary size: {len(course_dict)}")
            
            if self.debug_mode:
                self.debug_info['course_dict'] = course_dict
            
            # Step 9: Inject course names
            print("🏷️  Step 9: Injecting course names...")
            entries = self._inject_course_names(entries, course_dict)
            
            # Step 10: Validate
            print("[*] Step 10: Validating entries...")
            entries = self._validate_entries(entries)
            
            # Step 11: Deduplicate
            print("🗑️  Step 11: Deduplicating anchors...")
            entries = self._deduplicate_anchors(entries)
            print(f"   {len(entries)} unique entries")
            
            # Step 12: Build final output
            print("🎯 Step 12: Building final output...")
            final = self._build_final_entries(entries)
            print(f"[OK] Extracted {len(final)} attendance entries\n")
            
            if self.debug_mode:
                self.debug_info['final_entries'] = [e.dict() for e in final]
            
            return final
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            print(f"[FAIL] Error: {e}")
            return []
    
    def update_config(self, config: Dict):
        """Update OCR configuration and reset engine"""
        self.config.update(config)
        self.paddle_ocr = None  # Reset for lazy reload
        logger.info(f"OCR config updated: {config}")

