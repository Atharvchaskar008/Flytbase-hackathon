import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.api.upload import router as upload_router
from backend.api.timeline import router as timeline_router
from backend.api.search import router as search_router
from backend.api.clip import router as clip_router
from backend.api.status import router as status_router
from backend.api.investigation import router as investigation_router
from backend.api.ai_investigation import router as ai_investigation_router
from backend.api.summary import router as summary_router
from backend.core.config import settings
from backend.core.logger import logger
from database.database import init_db, test_connection

app = FastAPI(title="TRACE", version="0.1.0")

# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Startup validation and initialization"""
    print("\n" + "=" * 60)
    print("TRACE Backend Startup")
    print("=" * 60)
    
    # 1. Environment validation
    print("\n[1/5] Environment Validation")
    print(f"✓ Environment loaded")
    print(f"✓ Project root: {settings.PROJECT_ROOT}")
    print(f"✓ Debug mode: {settings.DEBUG}")
    
    # 2. Database connection
    print("\n[2/5] Database Connection")
    try:
        init_db()
        print("✓ PostgreSQL connected and initialized")
    except Exception as e:
        print(f"❌ Database initialization failed")
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)
    
    # 3. Directory setup
    print("\n[3/5] Directory Setup")
    directories = {
        "Upload": settings.UPLOAD_DIR,
        "Video": settings.VIDEO_DIR,
        "Clips": settings.PROJECT_ROOT / "storage" / "clips"
    }
    
    for name, directory in directories.items():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✓ {name} directory ready: {directory}")
        except Exception as e:
            print(f"❌ Failed to create {name} directory: {e}")
            logger.error(f"Failed to create {name} directory: {e}")
            sys.exit(1)
    
    # 4. Static files mounting
    print("\n[4/5] Static Files")
    clips_dir = settings.PROJECT_ROOT / "storage" / "clips"
    try:
        app.mount("/clips", StaticFiles(directory=str(clips_dir)), name="clips")
        print(f"✓ Clips mounted at /clips")
        logger.info(f"Mounted clips directory: {clips_dir}")
    except Exception as e:
        print(f"⚠ Warning: Could not mount clips directory: {e}")
        logger.warning(f"Could not mount clips directory: {e}")
    
    # 5. API routers
    print("\n[5/5] API Routes")
    print("✓ Upload API registered")
    print("✓ Timeline API registered")
    print("✓ Search API registered")
    print("✓ Clip API registered")
    print("✓ Status API registered")
    print("✓ Investigation API registered")
    print("✓ AI Investigation API registered")
    print("✓ Summary API registered")
    
    # Startup complete
    print("\n" + "=" * 60)
    print("✓ TRACE Backend Started Successfully")
    print("=" * 60)
    print(f"\nAPI Version: {app.version}")
    print(f"API Documentation: http://localhost:8000/docs")
    print(f"Health Check: http://localhost:8000/health")
    print(f"Database Health: http://localhost:8000/health/db")
    print("\n")
    
    logger.info("TRACE backend started successfully")


@app.get("/")
def root():
    return {"message": "TRACE API is running", "version": "0.1.0"}


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/health/db")
def db_health():
    try:
        message = test_connection()
        return {"status": "ok", "database": message}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "error", "database": str(e)}


# Include API routers
app.include_router(upload_router)
app.include_router(timeline_router)
app.include_router(search_router)
app.include_router(clip_router)
app.include_router(status_router)
app.include_router(investigation_router)
app.include_router(ai_investigation_router)
app.include_router(summary_router)
