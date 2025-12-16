"""
FastAPI OCR Backend for Hajri Attendance Tracker
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import time
import json
import os
from pathlib import Path
import logging
from typing import List, Dict
from dotenv import load_dotenv

from config import settings
from models import OCRResponse, HealthResponse, AttendanceEntry
from image_preprocessor import ImagePreprocessor
from table_extractor import TableExtractor
from ocr_config import OCRConfig, get_config, FAST_CONFIG, BALANCED_CONFIG, ACCURATE_CONFIG
from interactive_tuning import router as tuning_router, init_tuning

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
    description="Table-based attendance extraction for university dashboards",
    version="1.0.0",
    debug=settings.debug
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize processors with BALANCED config (recommended)
preprocessor = ImagePreprocessor()
current_config = BALANCED_CONFIG
extractor = TableExtractor(use_gpu=False, config=current_config.model_dump())
init_tuning(extractor, current_config)
logger.info("OCR service ready")


@app.get("/health")
async def health_check():
    """Health check endpoint for Render"""
    return {"status": "healthy", "service": "hajri-ocr-api"}

# Include tuning router
app.include_router(tuning_router)


@app.get("/tuning_ui.html")
async def serve_tuning_ui():
    """Serve the interactive tuning UI"""
    return FileResponse("tuning_ui.html")


@app.get("/tune.html")
async def serve_tune_guide():
    """Serve the tuning guide"""
    return FileResponse("tune.html")


@app.get("/test.html")
async def serve_test():
    """Serve the simple test interface"""
    return FileResponse("test.html")


@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "service": "Hajri OCR API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
        "test": "/test.html"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    paddle_ok = False
    tesseract_ok = False
    
    try:
        # Test PaddleOCR
        import paddleocr
        paddle_ok = True
    except Exception as e:
        logger.error(f"PaddleOCR not available: {e}")
    
    try:
        # Test Tesseract
        import pytesseract
        tesseract_ok = True
    except Exception as e:
        logger.warning(f"Tesseract not available: {e}")
    
    return HealthResponse(
        status="healthy" if paddle_ok else "degraded",
        paddle_available=paddle_ok,
        tesseract_available=tesseract_ok
    )


@app.post("/ocr/extract", response_model=OCRResponse)
async def extract_attendance(
    file: UploadFile = File(..., description="Dashboard screenshot (JPEG/PNG)")
):
    """
    Extract attendance data from dashboard screenshot
    
    Expects a table-based layout with columns:
    - Course Code
    - Class Type (LECT/LAB)
    - Present/Total
    - Percentage
    - Course Name
    """
    start_time = time.time()
    
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.content_type}. Expected image/*"
            )
        
        # Read file
        image_bytes = await file.read()
        
        # Check file size
        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb > settings.max_image_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {size_mb:.2f}MB (max: {settings.max_image_size_mb}MB)"
            )
        
        logger.info(f"Processing image: {file.filename} ({size_mb:.2f}MB)")
        
        # Preprocess image with screenshot mode (preserves table lines)
        processed_image = preprocessor.preprocess_screenshot(image_bytes)
        
        # Extract table and parse attendance entries (now done in one step)
        entries = extractor.extract_table_data(processed_image)
        
        if not entries:
            return OCRResponse(
                success=False,
                message="No attendance data found in image. Please ensure the image contains a clear attendance table.",
                entries=[],
                metadata={
                    "total_entries": 0,
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
            )
        
        # Calculate metadata
        processing_time = int((time.time() - start_time) * 1000)
        avg_confidence = sum(e.confidence for e in entries) / len(entries) if entries else 0.0
        
        logger.info(f"Extracted {len(entries)} entries in {processing_time}ms")
        
        return OCRResponse(
            success=True,
            message=f"Successfully extracted {len(entries)} attendance entries",
            entries=entries,
            metadata={
                "total_entries": len(entries),
                "avg_confidence": round(avg_confidence, 2),
                "processing_time_ms": processing_time,
                "confidence_threshold": settings.confidence_threshold
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {str(e)}"
        )


@app.post("/ocr/extract-base64", response_model=OCRResponse)
async def extract_attendance_base64(request: dict):
    """
    Extract attendance from base64-encoded image
    
    Request body:
    {
        "image": "base64_encoded_image_data"
    }
    """
    import base64
    
    try:
        if "image" not in request:
            raise HTTPException(status_code=400, detail="Missing 'image' field")
        
        # Decode base64
        image_data = request["image"]
        
        # Remove data URI prefix if present
        if "," in image_data:
            image_data = image_data.split(",")[1]
        
        image_bytes = base64.b64decode(image_data)
        
        # Create a mock UploadFile
        from io import BytesIO
        
        class MockUploadFile:
            def __init__(self, content: bytes):
                self.file = BytesIO(content)
                self.filename = "base64_image.png"
                self.content_type = "image/png"
            
            async def read(self):
                return self.file.read()
        
        mock_file = MockUploadFile(image_bytes)
        return await extract_attendance(mock_file)
        
    except Exception as e:
        logger.error(f"Base64 extraction failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/test/sample")
async def test_with_sample():
    """
    Test endpoint - will look for test images in test_images/ folder
    """
    import os
    from pathlib import Path
    
    test_dir = Path("test_images")
    
    if not test_dir.exists():
        return JSONResponse(
            status_code=404,
            content={
                "message": "No test_images/ folder found. Create one and add sample screenshots."
            }
        )
    
    results = []
    
    for image_file in test_dir.glob("*.{png,jpg,jpeg}"):
        try:
            with open(image_file, "rb") as f:
                image_bytes = f.read()
            
            class TestFile:
                def __init__(self, content: bytes, name: str):
                    self.content = content
                    self.filename = name
                    self.content_type = "image/png"
                
                async def read(self):
                    return self.content
            
            test_file = TestFile(image_bytes, image_file.name)
            result = await extract_attendance(test_file)
            
            results.append({
                "file": image_file.name,
                "success": result.success,
                "entries_count": len(result.entries),
                "avg_confidence": result.metadata.get("avg_confidence", 0)
            })
            
        except Exception as e:
            results.append({
                "file": image_file.name,
                "success": False,
                "error": str(e)
            })
    
    return {"results": results}


@app.get("/courses", response_model=dict)
async def get_courses():
    """Get all configured course codes and names"""
    try:
        config_path = Path(__file__).parent / "course_config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {
                "success": True,
                "courses": data.get('courses', {}),
                "total": len(data.get('courses', {}))
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading courses: {str(e)}")


@app.post("/courses/{code}", response_model=dict)
async def add_update_course(code: str, name: str, abbr: str = None):
    """Add or update a course code"""
    try:
        config_path = Path(__file__).parent / "course_config.json"
        
        # Load existing
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Update
        data['courses'][code.upper()] = {
            "name": name.upper(),
            "abbr": abbr.upper() if abbr else code.upper()
        }
        
        # Save
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Reload in extractor
        extractor.course_db = extractor._load_course_config()
        extractor.valid_course_codes = list(extractor.course_db.keys())
        
        return {
            "success": True,
            "message": f"Course {code} {'updated' if code in data['courses'] else 'added'}",
            "course": data['courses'][code.upper()]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving course: {str(e)}")


@app.delete("/courses/{code}", response_model=dict)
async def delete_course(code: str):
    """Delete a course code"""
    try:
        config_path = Path(__file__).parent / "course_config.json"
        
        # Load existing
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        code_upper = code.upper()
        if code_upper not in data['courses']:
            raise HTTPException(status_code=404, detail=f"Course {code} not found")
        
        # Delete
        del data['courses'][code_upper]
        
        # Save
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Reload in extractor
        extractor.course_db = extractor._load_course_config()
        extractor.valid_course_codes = list(extractor.course_db.keys())
        
        return {
            "success": True,
            "message": f"Course {code} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting course: {str(e)}")


@app.get("/courses.html")
async def serve_courses_manager():
    """Serve the course management UI"""
    return FileResponse("courses.html")



if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
