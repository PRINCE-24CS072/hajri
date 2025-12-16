"""
Configuration management for OCR backend
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # OCR
    ocr_engine: str = "paddle"  # paddle or tesseract
    confidence_threshold: float = 0.70
    max_image_size_mb: int = 10
    
    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    
    # Optional Tesseract path
    tesseract_cmd: str | None = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def origins_list(self) -> List[str]:
        """Parse comma-separated origins into list"""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


# Global settings instance
settings = Settings()
