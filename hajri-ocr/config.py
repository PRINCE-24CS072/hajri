"""Configuration management for OCR backend."""
from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # PaddleOCR-VL API Configuration
    paddleocr_vl_api_url: str = ""  # Set in .env or get from https://aistudio.baidu.com/paddleocr/task
    paddleocr_vl_api_token: str = ""  # Set in .env

    # PaddleOCR-VL API Options (PP-Structure / layout-parsing)
    paddleocr_markdown_ignore_labels: List[str] = [
        "header",
        "header_image",
        "footer",
        "footer_image",
        "number",
        "footnote",
        "aside_text",
    ]
    paddleocr_use_chart_recognition: bool = False

    # PP-Structure toggles
    paddleocr_use_region_detection: bool = True
    paddleocr_use_doc_orientation_classify: bool = False
    paddleocr_use_doc_unwarping: bool = False
    paddleocr_use_textline_orientation: bool = True
    paddleocr_use_seal_recognition: bool = True
    paddleocr_use_formula_recognition: bool = True
    paddleocr_use_table_recognition: bool = True

    # Layout detection tuning
    paddleocr_layout_threshold: float = 0.5
    paddleocr_layout_nms: bool = True
    paddleocr_layout_unclip_ratio: float = 1.0

    # Text detection tuning
    paddleocr_text_det_limit_type: str = "min"
    paddleocr_text_det_limit_side_len: int = 64
    paddleocr_text_det_thresh: float = 0.3
    paddleocr_text_det_box_thresh: float = 0.6
    paddleocr_text_det_unclip_ratio: float = 1.5
    paddleocr_text_rec_score_thresh: float = 0.0

    # Seal detection tuning
    paddleocr_seal_det_limit_type: str = "min"
    paddleocr_seal_det_limit_side_len: int = 736
    paddleocr_seal_det_thresh: float = 0.2
    paddleocr_seal_det_box_thresh: float = 0.6
    paddleocr_seal_det_unclip_ratio: float = 0.5
    paddleocr_seal_rec_score_thresh: float = 0.0

    # Table recognition tuning
    paddleocr_use_table_orientation_classify: bool = True
    paddleocr_use_ocr_results_with_table_cells: bool = True
    paddleocr_use_e2e_wired_table_rec_model: bool = False
    paddleocr_use_e2e_wireless_table_rec_model: bool = False
    paddleocr_use_wired_table_cells_trans_to_html: bool = True
    paddleocr_use_wireless_table_cells_trans_to_html: bool = False

    # Language
    paddleocr_parse_language: str = "default"
    
    # OCR Settings
    confidence_threshold: float = 0.70
    max_image_size_mb: int = 10
    
    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    
    class Config:
        env_file = str(Path(__file__).resolve().parent / ".env")
        case_sensitive = False
        extra = "ignore"
    
    @property
    def origins_list(self) -> List[str]:
        """Parse comma-separated origins into list"""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


# Global settings instance
settings = Settings()
