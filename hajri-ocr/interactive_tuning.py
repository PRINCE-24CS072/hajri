"""
Interactive OCR tuning endpoints - add to main.py
"""
from fastapi import APIRouter, Body
from ocr_config import OCRConfig, get_config, FAST_CONFIG, BALANCED_CONFIG, ACCURATE_CONFIG
from table_extractor import TableExtractor
from typing import Dict, Any

router = APIRouter(prefix="/config", tags=["Configuration"])

# Global extractor reference (will be set from main.py)
_extractor = None
_current_config = None


def init_tuning(extractor, config):
    """Initialize with current extractor and config"""
    global _extractor, _current_config
    _extractor = extractor
    _current_config = config


@router.get("/current")
async def get_current_config():
    """Get current OCR configuration"""
    return {
        "config": _current_config.model_dump() if _current_config else {},
        "description": "Current OCR settings (adjust for speed/accuracy tradeoff)"
    }


@router.post("/preset/{preset_name}")
async def set_preset(preset_name: str):
    """
    Switch to a performance preset
    
    Presets:
    - fast: ~1-2s per image (good for testing)
    - balanced: ~2-4s per image (recommended)
    - accurate: ~4-8s per image (best quality)
    """
    global _extractor, _current_config
    
    presets = {
        "fast": FAST_CONFIG,
        "balanced": BALANCED_CONFIG,
        "accurate": ACCURATE_CONFIG
    }
    
    if preset_name.lower() not in presets:
        return {"error": f"Unknown preset. Choose: {list(presets.keys())}"}
    
    new_config = presets[preset_name.lower()]
    
    # Reinitialize extractor with new config
    _extractor = TableExtractor(use_gpu=False, config=new_config.model_dump())
    _current_config = new_config
    
    return {
        "status": "success",
        "preset": preset_name,
        "config": new_config.model_dump(),
        "estimated_time": {
            "fast": "1-2s per image",
            "balanced": "2-4s per image",
            "accurate": "4-8s per image"
        }[preset_name.lower()]
    }


@router.post("/custom")
async def set_custom_config(config: Dict[str, Any] = Body(...)):
    """
    Set custom OCR configuration
    
    Example:
    {
        "use_angle_cls": false,
        "det_limit_side_len": 640,
        "det_db_thresh": 0.3,
        "drop_score": 0.3,
        "cpu_threads": 4
    }
    """
    global _extractor, _current_config
    
    try:
        # Validate and create config
        custom_config = OCRConfig(**config)
        
        # Reinitialize extractor
        _extractor = TableExtractor(use_gpu=False, config=custom_config.model_dump())
        _current_config = custom_config
        
        return {
            "status": "success",
            "config": custom_config.model_dump()
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/presets")
async def list_presets():
    """List all available presets with their settings"""
    return {
        "fast": {
            "config": FAST_CONFIG.model_dump(),
            "estimated_time": "1-2s per image",
            "description": "Maximum speed, good for testing"
        },
        "balanced": {
            "config": BALANCED_CONFIG.model_dump(),
            "estimated_time": "2-4s per image",
            "description": "Recommended balance of speed and accuracy"
        },
        "accurate": {
            "config": ACCURATE_CONFIG.model_dump(),
            "estimated_time": "4-8s per image",
            "description": "Best quality, slower processing"
        }
    }


@router.get("/tuning-guide")
async def get_tuning_guide():
    """
    Get interactive tuning guide
    """
    return {
        "speed_optimization": {
            "use_angle_cls": {
                "description": "Detect rotated text",
                "recommendation": "Set to false for 30-40% speed boost (dashboard screenshots are usually straight)",
                "values": "true/false"
            },
            "det_limit_side_len": {
                "description": "Detection input image size",
                "recommendation": "640 = fastest, 960 = balanced, 1280+ = accurate",
                "values": "640-1920"
            },
            "max_image_size": {
                "description": "Max image dimension before resize",
                "recommendation": "960 = fast, 1280 = balanced, 1920 = accurate",
                "values": "960-2560"
            },
            "cpu_threads": {
                "description": "Number of CPU threads",
                "recommendation": "4-6 for most systems",
                "values": "2-8"
            }
        },
        "accuracy_tuning": {
            "drop_score": {
                "description": "Minimum confidence to keep text",
                "recommendation": "0.25 = keep more, 0.5 = strict quality",
                "values": "0.2-0.7"
            },
            "det_db_thresh": {
                "description": "Text detection sensitivity",
                "recommendation": "0.25 = find more text, 0.35 = stricter",
                "values": "0.2-0.5"
            },
            "min_confidence": {
                "description": "Table detection confidence",
                "recommendation": "30 = find more tables, 50 = stricter",
                "values": "30-70"
            }
        },
        "quick_tips": [
            "Start with 'balanced' preset",
            "If too slow: try 'fast' preset",
            "If missing text: lower drop_score to 0.25",
            "If 'no table found': lower min_confidence to 35",
            "Dashboard screenshots don't need angle detection (set use_angle_cls=false)"
        ]
    }
