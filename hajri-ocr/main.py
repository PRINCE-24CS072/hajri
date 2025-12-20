"""
FastAPI OCR Backend for Hajri Attendance Tracker
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
from pathlib import Path
import logging
import json
from typing import Optional
from dotenv import load_dotenv

from config import settings
from models import OCRResponse, AttendanceEntry
from image_preprocessor import ImagePreprocessor
from table_extractor import TableExtractor

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'warning').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Hajri OCR API",
    description="Attendance extraction from university dashboard screenshots",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize processors
preprocessor = ImagePreprocessor()
extractor = TableExtractor(use_gpu=False)
logger.info("OCR service ready")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "hajri-ocr-api"}


@app.get("/test.html")
async def serve_test():
    """Serve test UI"""
    return FileResponse("test.html")


@app.get("/tuning.html")
async def serve_tuning():
    """Serve interactive tuning UI"""
    return FileResponse("tuning.html")


@app.get("/courses.html")
async def serve_courses_manager():
    """Serve course management UI"""
    return FileResponse("courses.html")


@app.post("/ocr/extract", response_model=OCRResponse)
async def extract_attendance(file: UploadFile = File(...)):
    """Extract attendance entries from dashboard screenshot"""
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(400, "File must be an image")
        
        # Read and validate file size
        image_bytes = await file.read()
        size_mb = len(image_bytes) / (1024 * 1024)
        
        if size_mb > settings.max_image_size_mb:
            raise HTTPException(400, f"File too large: {size_mb:.2f}MB")
        
        # Preprocess image with modal detection
        logger.info("Preprocessing image with modal detection...")
        processed_image, preprocess_debug = preprocessor.preprocess_screenshot(
            image_bytes,
            ocr_engine=extractor._get_ocr(),  # Reuse OCR engine
            detect_modal=True  # Enable modal detection
        )
        
        logger.info(f"Preprocessing complete. Modal detected: {preprocess_debug.get('modal_detected')}")
        
        # Extract attendance entries
        entries = extractor.extract_table_data(processed_image)
        
        return OCRResponse(
            success=True,
            message=f"Extracted {len(entries)} attendance entries",
            entries=entries
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR failed: {str(e)}")
        raise HTTPException(500, f"OCR failed: {str(e)}")


@app.post("/ocr/extract/tuning")
async def extract_attendance_tuning(
    file: UploadFile = File(...),
    x_tuning_params: Optional[str] = Header(None)
):
    """Extract with custom tuning parameters and debug output"""
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(400, "File must be an image")
        
        # Read and validate file size
        image_bytes = await file.read()
        size_mb = len(image_bytes) / (1024 * 1024)
        
        if size_mb > settings.max_image_size_mb:
            raise HTTPException(400, f"File too large: {size_mb:.2f}MB")
        
        # Parse tuning parameters
        params = {}
        if x_tuning_params:
            try:
                params = json.loads(x_tuning_params)
            except json.JSONDecodeError:
                logger.warning("Invalid tuning params JSON")
        
        # Apply tuning parameters to extractor
        if 'region_split' in params:
            extractor.region_split_threshold = float(params['region_split'])
        if 'row_tolerance' in params:
            extractor.row_tolerance = float(params['row_tolerance'])
        if 'min_tokens' in params:
            extractor.min_tokens_per_row = int(params['min_tokens'])
        if 'det_thresh' in params:
            extractor.config['det_db_thresh'] = float(params['det_thresh'])
            extractor.paddle_ocr = None  # Force reload
        if 'box_thresh' in params:
            extractor.config['det_db_box_thresh'] = float(params['box_thresh'])
            extractor.paddle_ocr = None  # Force reload
        if 'drop_score' in params:
            extractor.config['drop_score'] = float(params['drop_score'])
            extractor.paddle_ocr = None  # Force reload
        
        # Preprocess image
        processed_image = preprocessor.preprocess_screenshot(image_bytes)
        
        # Extract with debug mode enabled
        debug_mode = params.get('debug', False)
        entries = extractor.extract_table_data(processed_image, debug=debug_mode)
        
        # Build response with debug info
        response = {
            "success": True,
            "message": f"Extracted {len(entries)} attendance entries",
            "entries": [entry.model_dump() for entry in entries],
            "debug": extractor.debug_info if debug_mode else {},
            "params_used": {
                "region_split": extractor.region_split_threshold,
                "row_tolerance": extractor.row_tolerance,
                "min_tokens": extractor.min_tokens_per_row,
                "det_thresh": extractor.config['det_db_thresh'],
                "box_thresh": extractor.config['det_db_box_thresh'],
                "drop_score": extractor.config['drop_score']
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tuning extraction failed: {str(e)}")
        raise HTTPException(500, f"Extraction failed: {str(e)}")


@app.get("/courses")
async def get_courses():
    """Get all configured courses"""
    try:
        config_path = Path("course_config.json")
        if not config_path.exists():
            return {"courses": {}}
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config
    except Exception as e:
        logger.error(f"Failed to load courses: {str(e)}")
        return {"courses": {}}


@app.post("/courses/{code}")
async def add_course(code: str, course: dict):
    """Add or update a course"""
    try:
        config_path = Path("course_config.json")
        
        # Load existing config
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {"courses": {}}
        
        # Add/update course
        config["courses"][code.upper()] = {
            "name": course.get("name", ""),
            "abbr": course.get("abbr", "")
        }
        
        # Save
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Reload extractor's course database
        extractor.course_db = config.get("courses", {})
        
        return {"success": True, "message": f"Course {code} added/updated"}
        
    except Exception as e:
        logger.error(f"Failed to add course: {str(e)}")
        raise HTTPException(500, f"Failed to add course: {str(e)}")


@app.delete("/courses/{code}")
async def delete_course(code: str):
    """Delete a course"""
    try:
        config_path = Path("course_config.json")
        
        if not config_path.exists():
            raise HTTPException(404, "Course configuration not found")
        
        # Load config
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Delete course
        if code.upper() in config.get("courses", {}):
            del config["courses"][code.upper()]
            
            # Save
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Reload extractor's course database
            extractor.course_db = config.get("courses", {})
            
            return {"success": True, "message": f"Course {code} deleted"}
        else:
            raise HTTPException(404, f"Course {code} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete course: {str(e)}")
        raise HTTPException(500, f"Failed to delete course: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

