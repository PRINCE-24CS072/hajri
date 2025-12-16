"""
OCR Configuration with Interactive Tuning
Users can adjust these settings for speed vs accuracy tradeoff
"""
from pydantic import BaseModel, Field
from typing import Optional


class OCRConfig(BaseModel):
    """
    Interactive OCR Configuration
    
    SPEED PRESETS:
    - FAST: ~1-2s per image (good for testing)
    - BALANCED: ~2-4s per image (recommended)
    - ACCURATE: ~4-8s per image (best quality)
    """
    
    # === SPEED TUNING ===
    use_angle_cls: bool = Field(
        default=False,  # Changed from True - saves 30-40% time!
        description="Detect text rotation (disable for faster processing)"
    )
    
    det: bool = Field(
        default=True,
        description="Enable text detection (required for tables)"
    )
    
    rec: bool = Field(
        default=True,
        description="Enable text recognition"
    )
    
    # === IMAGE SIZE TUNING ===
    max_image_size: int = Field(
        default=1280,  # Reduced from default 2560
        description="Max dimension before resize (smaller = faster, 960-1920 recommended)"
    )
    
    det_limit_side_len: int = Field(
        default=960,  # Reduced from default 960
        description="Detection input size (640-1280, smaller = faster)"
    )
    
    # === DETECTION TUNING ===
    det_db_thresh: float = Field(
        default=0.3,  # Default 0.3
        description="Text detection threshold (lower = find more text, 0.2-0.5)"
    )
    
    det_db_box_thresh: float = Field(
        default=0.5,  # Lowered from 0.6
        description="Box filtering threshold (lower = more boxes, 0.4-0.7)"
    )
    
    det_db_unclip_ratio: float = Field(
        default=1.5,  # Default 1.5
        description="Box expansion ratio (1.2-2.0)"
    )
    
    # === RECOGNITION TUNING ===
    rec_batch_num: int = Field(
        default=6,  # Default 6
        description="Batch size for recognition (higher = faster but more memory)"
    )
    
    drop_score: float = Field(
        default=0.3,  # Lowered from 0.5 for attendance data
        description="Minimum confidence score (0.2-0.7, lower = keep more results)"
    )
    
    # === TABLE DETECTION TUNING ===
    min_confidence: int = Field(
        default=40,  # Lowered from 50
        description="Table detection confidence (30-70, lower = find more tables)"
    )
    
    implicit_rows: bool = Field(
        default=True,
        description="Detect rows without clear borders"
    )
    
    borderless_tables: bool = Field(
        default=True,
        description="Detect tables without borders"
    )
    
    # === HARDWARE ===
    use_gpu: bool = Field(
        default=False,
        description="Use GPU acceleration (requires CUDA)"
    )
    
    enable_mkldnn: bool = Field(
        default=False,  # Can cause issues on some CPUs
        description="Use Intel MKL-DNN acceleration"
    )
    
    cpu_threads: int = Field(
        default=4,  # Reduced from 10
        description="Number of CPU threads (2-8 recommended)"
    )


# === PRESET CONFIGURATIONS ===

FAST_CONFIG = OCRConfig(
    use_angle_cls=False,
    max_image_size=960,
    det_limit_side_len=640,
    det_db_thresh=0.35,
    det_db_box_thresh=0.45,
    rec_batch_num=8,
    drop_score=0.35,
    min_confidence=35,
    cpu_threads=4
)

BALANCED_CONFIG = OCRConfig(
    use_angle_cls=False,
    max_image_size=1280,
    det_limit_side_len=960,
    det_db_thresh=0.3,
    det_db_box_thresh=0.5,
    rec_batch_num=6,
    drop_score=0.3,
    min_confidence=40,
    cpu_threads=4
)

ACCURATE_CONFIG = OCRConfig(
    use_angle_cls=True,
    max_image_size=1920,
    det_limit_side_len=1280,
    det_db_thresh=0.25,
    det_db_box_thresh=0.55,
    rec_batch_num=4,
    drop_score=0.25,
    min_confidence=45,
    cpu_threads=6
)



def get_config(preset: str = "balanced") -> OCRConfig:
    """Get configuration by preset name"""
    presets = {
        "fast": FAST_CONFIG,
        "balanced": BALANCED_CONFIG,
        "accurate": ACCURATE_CONFIG
    }
    return presets.get(preset.lower(), BALANCED_CONFIG)