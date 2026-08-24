import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "PackSure AI – Legal Metrology Compliance Checker"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Database: Supports PostgreSQL or SQLite fallback
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./packsure.db")
    
    # Uploads directory
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    
    # AI & Rule configurations
    MIN_COMPLIANCE_SCORE_PASS: float = 80.0
    
    class Config:
        case_sensitive = True

settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
