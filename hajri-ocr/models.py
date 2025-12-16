"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class AttendanceEntry(BaseModel):
    """Single attendance record extracted from table"""
    course_code: str = Field(..., description="Course code (e.g., CEUC201/FSE)")
    course_name: str = Field(..., description="Full course name")
    class_type: str = Field(..., description="LECT or LAB")
    present: int = Field(..., ge=0, description="Classes attended")
    total: int = Field(..., ge=0, description="Total classes conducted")
    percentage: float = Field(..., ge=0, le=100, description="Attendance percentage")
    confidence: float = Field(..., ge=0, le=1, description="Extraction confidence (0-1)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "course_code": "CEUC201/FSE",
                "course_name": "FUNDAMENTALS OF SOFTWARE ENGINEERING",
                "class_type": "LECT",
                "present": 12,
                "total": 15,
                "percentage": 80.0,
                "confidence": 0.95
            }
        }


class OCRResponse(BaseModel):
    """Response from OCR extraction"""
    success: bool
    message: str
    entries: List[AttendanceEntry] = []
    metadata: dict = Field(default_factory=dict)
    processed_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Extracted 7 attendance entries",
                "entries": [],
                "metadata": {
                    "total_rows": 7,
                    "filtered_rows": 0,
                    "avg_confidence": 0.89,
                    "processing_time_ms": 1234
                },
                "processed_at": "2025-12-16T10:30:00"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    paddle_available: bool
    tesseract_available: bool
    version: str = "1.0.0"
