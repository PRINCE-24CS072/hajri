"""
PaddleOCR-VL API-based Table Extraction
Uses Baidu's hosted PaddleOCR-VL API for document analysis
"""
import re
import logging
import base64
import difflib
import requests
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
import numpy as np
import cv2

from models import AttendanceEntry

logger = logging.getLogger(__name__)


class TableExtractor:
    """
    PaddleOCR-VL API-based extraction
    
    Uses Baidu's hosted PaddleOCR-VL API to parse attendance tables
    """
    
    def __init__(self, api_url: str, api_token: str, api_options: Optional[Dict[str, Any]] = None):
        """Initialize API configuration"""
        self.api_url = api_url
        self.api_token = api_token
        self.api_options = api_options or {}
        # Optional pre-matched course map injected by the app (e.g., from course_config.json)
        self.course_db: Dict[str, Any] = {}
        # Used when matching OCR course names/abbrs to configured courses
        self.course_fuzzy_match_threshold: float = 0.75
    
    def _encode_image(self, image: np.ndarray) -> str:
        """Encode image to base64 string"""
        _, buffer = cv2.imencode('.png', image)
        return base64.b64encode(buffer.tobytes()).decode('ascii')

    def _build_payload(self, *, file_data: str) -> Dict[str, Any]:
        """Build PaddleOCR PP-Structure layout-parsing payload."""
        required_payload: Dict[str, Any] = {
            "file": file_data,
            "fileType": 1,  # image
        }

        # Default optional payload aligned with PaddleOCR PP-Structure layout-parsing API.
        optional_payload: Dict[str, Any] = {
            "markdownIgnoreLabels": [
                "header",
                "header_image",
                "footer",
                "footer_image",
                "number",
                "footnote",
                "aside_text",
            ],
            "useChartRecognition": False,

            "useRegionDetection": True,
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useTextlineOrientation": True,
            "useSealRecognition": True,
            "useFormulaRecognition": True,
            "useTableRecognition": True,

            "layoutThreshold": 0.5,
            "layoutNms": True,
            "layoutUnclipRatio": 1,

            "textDetLimitType": "min",
            "textDetLimitSideLen": 64,
            "textDetThresh": 0.3,
            "textDetBoxThresh": 0.6,
            "textDetUnclipRatio": 1.5,
            "textRecScoreThresh": 0,

            "sealDetLimitType": "min",
            "sealDetLimitSideLen": 736,
            "sealDetThresh": 0.2,
            "sealDetBoxThresh": 0.6,
            "sealDetUnclipRatio": 0.5,
            "sealRecScoreThresh": 0,

            "useTableOrientationClassify": True,
            "useOcrResultsWithTableCells": True,
            "useE2eWiredTableRecModel": False,
            "useE2eWirelessTableRecModel": False,
            "useWiredTableCellsTransToHtml": True,
            "useWirelessTableCellsTransToHtml": False,

            "parseLanguage": "default",
        }

        # Allow caller to override any optional keys (e.g., from Settings).
        for k, v in (self.api_options or {}).items():
            if v is not None:
                optional_payload[k] = v

        return {**required_payload, **optional_payload}
    
    def _call_api(self, image: np.ndarray, *, file_data: Optional[str] = None) -> Dict:
        """Call PaddleOCR-VL API"""
        file_data = file_data or self._encode_image(image)
        
        headers = {
            "Authorization": f"token {self.api_token}",
            "Content-Type": "application/json"
        }
        
        payload = self._build_payload(file_data=file_data)
        
        response = requests.post(self.api_url, json=payload, headers=headers, timeout=60)
        
        if response.status_code != 200:
            raise RuntimeError(f"API error: {response.status_code}")
        
        result = response.json()
        if result.get("errorCode") != 0:
            raise RuntimeError(f"API error: {result.get('errorMsg')}")
        
        return result["result"]
    
    def _parse_markdown_to_entries(self, markdown_text: str) -> List[AttendanceEntry]:
        """
        Parse HTML tables from markdown output to extract attendance entries
        
        The API returns a single table with 6 columns:
        [Course | Class Type | Present/Total | Percentage | Course Code | Course Name]
        
        IMPORTANT: The right-side columns (Course Code/Name) are shifted up by 1 row
        relative to the left-side columns (attendance data). We need to match them correctly.
        """
        entries = []
        
        try:
            soup = BeautifulSoup(markdown_text, 'html.parser')
            tables = soup.find_all('table')
            
            logger.info(f"Found {len(tables)} tables in markdown")
            
            if not tables:
                return entries

            def _is_attendance_fraction(text: str) -> bool:
                return bool(re.search(r'\b\d+\s*/\s*\d+\b', text or ""))

            def _looks_like_course_name(text: str) -> bool:
                if not text:
                    return False
                t = text.strip()
                if _is_attendance_fraction(text):
                    return False
                # Reject common class-type tokens that appear next to course codes.
                if t.upper() in {"LECT", "LAB", "TUT", "PRACT", "PRACTICAL", "THEORY"}:
                    return False
                # Needs some letters to be a plausible name
                if not re.search(r'[A-Za-z]{3,}', t):
                    return False
                # Avoid short single tokens (e.g., LECT/OOP/FSE) unless they look like a real title.
                # Course titles almost always have spaces OR are long enough.
                return (" " in t) or (len(t) >= 10)

            def _extract_course_code(text: str) -> Optional[str]:
                if not text:
                    return None
                code_match = re.search(r'\b([A-Z]+\d+)\b', text.strip())
                return code_match.group(1) if code_match else None

            # Build a course name lookup from tables OTHER than the attendance table.
            # This avoids mapping course_code -> class_type when the attendance table is scanned.
            # Priority order later: OCR-derived map -> pre-matched config map -> Unknown.
            course_names: Dict[str, str] = {}

            for t in tables[1:]:
                for row in t.find_all('tr'):
                    # Consider both th and td to catch small "code/name" reference tables
                    cells = row.find_all(['th', 'td'])
                    if len(cells) < 2:
                        continue
                    texts = [c.get_text(strip=True) for c in cells]

                    # Scan adjacent pairs for a (code, name) pattern.
                    for i in range(len(texts) - 1):
                        code = _extract_course_code(texts[i])
                        if not code:
                            continue
                        name = texts[i + 1]
                        if _looks_like_course_name(name):
                            course_names.setdefault(code, name)

                    # Also handle "CODE: Name" in one cell.
                    for text in texts:
                        if not text:
                            continue
                        m = re.match(r'^\s*([A-Z]+\d+)\s*[:\-]\s*(.+?)\s*$', text)
                        if m and _looks_like_course_name(m.group(2)):
                            course_names.setdefault(m.group(1), m.group(2))
            
            # Process first table (attendance table)
            table = tables[0]
            rows = table.find_all('tr')
            
            if len(rows) < 2:
                logger.warning("Table has no data rows")
                return entries
            
            # Also learn from the right-side columns (cols 4-5) of the attendance table when present.
            for row in rows[1:]:  # Skip header
                cells = row.find_all('td')
                if len(cells) >= 6:
                    right_course_code_text = cells[4].get_text(strip=True)
                    right_course_name = cells[5].get_text(strip=True)
                    
                    # Extract course code (e.g., "CEUE203 / OOP" -> "CEUE203")
                    code = _extract_course_code(right_course_code_text)
                    if code and right_course_name:
                        course_names.setdefault(code, right_course_name)
            
            # Now parse attendance data from left-side columns (cols 0-3)
            for row_idx, row in enumerate(rows[1:], 1):
                cells = row.find_all('td')
                
                if len(cells) < 4:
                    continue
                
                # Extract: Course | Class Type | Present/Total | Percentage
                course_text = cells[0].get_text(strip=True)
                class_type = cells[1].get_text(strip=True)
                attendance_text = cells[2].get_text(strip=True)
                
                # Parse course code (e.g., "CEUC201 / FSE" -> "CEUC201")
                course_code_match = re.match(r'([A-Z]+\d+)', course_text)
                if not course_code_match:
                    continue
                extracted_course_code = course_code_match.group(1)

                # Parse course abbr (e.g., "CEUC201 / FSE" -> "FSE")
                extracted_abbr = None
                abbr_match = re.search(r'/\s*([A-Za-z0-9\-]+)', course_text)
                if abbr_match:
                    extracted_abbr = abbr_match.group(1).strip().upper()
                
                # Parse attendance (e.g., "28 / 39" -> present=28, total=39)
                attendance_pattern = re.compile(r'(\d+)\s*/\s*(\d+)')
                attendance_match = attendance_pattern.search(attendance_text)
                
                if not attendance_match:
                    logger.warning(f"Row {row_idx}: Cannot parse attendance '{attendance_text}'")
                    continue
                
                present = int(attendance_match.group(1))
                total = int(attendance_match.group(2))
                percentage = (present / total * 100) if total > 0 else 0.0
                
                # Lookup course name using the course code
                course_name_source = "unknown"
                ocr_course_name = course_names.get(extracted_course_code)

                # Build config indexes (code -> name/abbr, abbr -> codes)
                config_courses: Dict[str, Dict[str, str]] = {}
                abbr_to_codes: Dict[str, List[str]] = {}
                if isinstance(getattr(self, 'course_db', None), dict):
                    for code, val in self.course_db.items():
                        if not isinstance(code, str):
                            continue
                        if isinstance(val, str):
                            name = val
                            abbr = ""
                        elif isinstance(val, dict):
                            name = (val.get('name') or val.get('course_name') or val.get('title') or "")
                            abbr = (val.get('abbr') or "")
                        else:
                            continue
                        code_u = code.strip().upper()
                        name = name.strip()
                        abbr_u = abbr.strip().upper()
                        if not code_u:
                            continue
                        config_courses[code_u] = {"name": name, "abbr": abbr_u}
                        if abbr_u:
                            abbr_to_codes.setdefault(abbr_u, []).append(code_u)

                def _norm(s: str) -> str:
                    # Upper, collapse whitespace, drop punctuation for more stable matching
                    s = (s or "").upper()
                    s = re.sub(r'[^A-Z0-9\s]+', ' ', s)
                    s = re.sub(r'\s+', ' ', s).strip()
                    return s

                def _best_name_match(ocr_name: str) -> Optional[str]:
                    """Return best matching course code from config based on OCR name."""
                    if not ocr_name or not config_courses:
                        return None
                    o = _norm(ocr_name)
                    if not o:
                        return None
                    best_code = None
                    best_score = 0.0
                    for code_u, meta in config_courses.items():
                        cn = _norm(meta.get('name') or "")
                        if not cn:
                            continue
                        # Fast path for truncation: OCR name is a prefix/substr of full config name
                        if cn.startswith(o) or (o in cn and len(o) >= 12):
                            score = 1.0
                        else:
                            score = difflib.SequenceMatcher(a=o, b=cn).ratio()
                        if score > best_score:
                            best_score = score
                            best_code = code_u

                    threshold = getattr(self, 'course_fuzzy_match_threshold', 0.75)
                    return best_code if best_code and best_score >= float(threshold) else None

                resolved_course_code = extracted_course_code
                resolved_shortname = extracted_abbr or ""

                # 1) Exact code match in config
                config_meta = config_courses.get(extracted_course_code)
                if config_meta and config_meta.get('name'):
                    course_name = config_meta['name']
                    course_name_source = "config"
                    resolved_shortname = (config_meta.get('abbr') or resolved_shortname or "")

                # 2) Match by abbr (helps when OCR misreads the course code but gets /FSE correct)
                elif extracted_abbr and extracted_abbr in abbr_to_codes and len(abbr_to_codes[extracted_abbr]) == 1:
                    matched_code = abbr_to_codes[extracted_abbr][0]
                    matched_meta = config_courses.get(matched_code) or {}
                    if matched_meta.get('name'):
                        resolved_course_code = matched_code
                        course_name = matched_meta['name']
                        course_name_source = "config"
                        resolved_shortname = (matched_meta.get('abbr') or extracted_abbr or resolved_shortname or "")

                # 3) Fuzzy match by OCR course name (helps when code is wrong and name is partial)
                elif ocr_course_name:
                    matched_code = _best_name_match(ocr_course_name)
                    if matched_code:
                        matched_meta = config_courses.get(matched_code) or {}
                        if matched_meta.get('name'):
                            resolved_course_code = matched_code
                            course_name = matched_meta['name']
                            course_name_source = "config"
                            resolved_shortname = (matched_meta.get('abbr') or resolved_shortname or "")
                        else:
                            course_name = ocr_course_name
                            course_name_source = "ocr"
                    else:
                        course_name = ocr_course_name
                        course_name_source = "ocr"
                else:
                    course_name = "Unknown"
                
                entries.append(AttendanceEntry(
                    course_code=resolved_course_code,
                    shortname=resolved_shortname,
                    course_name=course_name,
                    course_name_source=course_name_source,
                    class_type=class_type or "LECT",
                    present=present,
                    total=total,
                    percentage=percentage,
                    confidence=1.0
                ))
        
        except Exception as e:
            logger.error(f"Error parsing HTML tables: {e}", exc_info=True)
        
        return entries
    
    def extract_table_data(self, image: np.ndarray) -> List[AttendanceEntry]:
        """Extract attendance entries using PaddleOCR-VL API"""
        try:
            api_result = self._call_api(image)
            
            if not api_result.get("layoutParsingResults"):
                logger.warning("No parsing results from API")
                return []
            
            # Extract markdown from first page
            parsing_results = api_result["layoutParsingResults"][0]
            markdown_text = parsing_results.get("markdown", {}).get("text", "")
            
            if not markdown_text:
                logger.warning("Empty markdown output")
                return []
            
            # Save markdown for debugging
            with open("last_markdown.txt", "w", encoding="utf-8") as f:
                f.write(markdown_text)
            
            logger.info(f"Step 2: Parsing markdown ({len(markdown_text)} chars)...")
            
            entries = self._parse_markdown_to_entries(markdown_text)
            
            logger.info(f"✅ Extracted {len(entries)} attendance entries")
            return entries
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            return []
