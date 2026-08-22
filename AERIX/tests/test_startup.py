"""
Test startup configuration without starting the server
This validates that all imports work correctly
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Testing TRACE Backend Startup Configuration")
print("=" * 60)

# Test 1: Environment loading
print("\n[Test 1] Environment Loading")
try:
    from backend.core.config import settings
    print("✓ Config loaded successfully")
    print(f"  PROJECT_ROOT: {settings.PROJECT_ROOT}")
    print(f"  DATABASE_URL: {'Set' if settings.DATABASE_URL else 'Missing'}")
except Exception as e:
    print(f"❌ Config loading failed: {e}")
    sys.exit(1)

# Test 2: Logger
print("\n[Test 2] Logger")
try:
    from backend.core.logger import logger
    logger.info("Test log message")
    print("✓ Logger initialized")
except Exception as e:
    print(f"❌ Logger initialization failed: {e}")
    sys.exit(1)

# Test 3: Database session
print("\n[Test 3] Database Session")
try:
    from database.session import engine, SessionLocal
    print("✓ Database engine created")
    print("✓ SessionLocal created")
except Exception as e:
    print(f"❌ Database session creation failed: {e}")
    sys.exit(1)

# Test 4: Database models
print("\n[Test 4] Database Models")
try:
    from database.base import Base
    import database.models
    print("✓ Base class imported")
    print("✓ Models imported")
    print(f"  Tables defined: {len(Base.metadata.tables)}")
except Exception as e:
    print(f"❌ Model import failed: {e}")
    sys.exit(1)

# Test 5: Database functions
print("\n[Test 5] Database Functions")
try:
    from database.database import init_db, test_connection
    print("✓ init_db imported")
    print("✓ test_connection imported")
except Exception as e:
    print(f"❌ Database function import failed: {e}")
    sys.exit(1)

# Test 6: FastAPI app
print("\n[Test 6] FastAPI Application")
try:
    from backend.main import app
    print("✓ FastAPI app created")
    print(f"  Title: {app.title}")
    print(f"  Version: {app.version}")
    print(f"  Routes: {len(app.routes)}")
except Exception as e:
    print(f"❌ FastAPI app creation failed: {e}")
    sys.exit(1)

# Test 7: API routers
print("\n[Test 7] API Routers")
try:
    from backend.api.upload import router as upload_router
    from backend.api.timeline import router as timeline_router
    from backend.api.search import router as search_router
    from backend.api.clip import router as clip_router
    print("✓ Upload router imported")
    print("✓ Timeline router imported")
    print("✓ Search router imported")
    print("✓ Clip router imported")
except Exception as e:
    print(f"❌ Router import failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✓ All startup tests passed!")
print("=" * 60)
print("\nConfiguration is valid. Backend can start.")
print("\nNext steps:")
print("1. Check PostgreSQL: python check_postgres.py")
print("2. Start backend: uvicorn backend.main:app --reload")
