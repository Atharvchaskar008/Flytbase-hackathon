import os
from pathlib import Path
import sys

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

# Load .env from multiple possible locations (project root first, then backend)
env_loaded = False
for env_path in [PROJECT_ROOT / ".env", BACKEND_DIR / ".env"]:
    if env_path.exists():
        load_dotenv(env_path)
        env_loaded = True
        print(f"[OK] Loaded environment from: {env_path}")
        break

if not env_loaded:
    print(f"[WARNING] No .env file found in {PROJECT_ROOT} or {BACKEND_DIR}")


class Settings:
    def __init__(self):
        # Load DATABASE_URL
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "")
        
        if not self.DATABASE_URL:
            print("\n[ERROR] DATABASE_URL not found in environment variables")
            print("Expected format: postgresql://user:password@host:port/database")
            print(f"Check .env file in: {PROJECT_ROOT}")
            sys.exit(1)
        
        # Mask password for logging
        masked_url = self._mask_password(self.DATABASE_URL)
        print(f"[OK] DATABASE_URL loaded: {masked_url}")
        
        # Load other settings
        self.REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.DEBUG: bool = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"}
        self.PROJECT_ROOT: Path = PROJECT_ROOT
        self.UPLOAD_DIR: Path = PROJECT_ROOT / "storage" / "uploads"
        self.VIDEO_DIR: Path = PROJECT_ROOT / "storage" / "videos"
        self.KEYFRAME_DIR: Path = PROJECT_ROOT / "storage" / "keyframes"
        self.ALLOWED_VIDEO_EXTENSIONS: set[str] = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
        self.MAX_VIDEO_SIZE: int = 500 * 1024 * 1024  # 500 MB limit
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        
        # LLM Settings
        self.GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
        self.USE_MOCK_LLM: bool = not bool(self.GEMINI_API_KEY)
        
        print(f"[OK] Upload directory: {self.UPLOAD_DIR}")
        print(f"[OK] Video directory: {self.VIDEO_DIR}")
        print(f"[OK] Log level: {self.LOG_LEVEL}")
    
    def _mask_password(self, url: str) -> str:
        """Mask password in database URL for safe logging"""
        if "://" not in url:
            return url
        
        try:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                credentials, host_part = rest.split("@", 1)
                if ":" in credentials:
                    user, _ = credentials.split(":", 1)
                    return f"{scheme}://{user}:****@{host_part}"
                else:
                    return f"{scheme}://{credentials}@{host_part}"
            return url
        except Exception:
            return url


settings = Settings()

