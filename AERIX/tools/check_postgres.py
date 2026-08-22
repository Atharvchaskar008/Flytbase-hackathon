"""
Check PostgreSQL connection before starting the backend
Run this to diagnose database connection issues
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"[OK] Loaded .env from {env_file}")
else:
    print(f"❌ No .env file found at {env_file}")
    sys.exit(1)

# Get DATABASE_URL
database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL not found in .env")
    sys.exit(1)

# Mask password
def mask_password(url: str) -> str:
    if "://" not in url:
        return url
    try:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            credentials, host_part = rest.split("@", 1)
            if ":" in credentials:
                user, _ = credentials.split(":", 1)
                return f"{scheme}://{user}:****@{host_part}"
        return url
    except Exception:
        return url

print(f"✓ DATABASE_URL: {mask_password(database_url)}")

# Test connection
print("\nTesting PostgreSQL connection...")
try:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        print(f"✓ Connected to PostgreSQL")
        print(f"  Version: {version.split(',')[0]}")
        
        # Check if database exists and has tables
        result = connection.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """))
        table_count = result.fetchone()[0]
        print(f"  Tables in database: {table_count}")
        
        if table_count == 0:
            print("\n⚠ Warning: No tables found. Run database initialization:")
            print("  python -c \"from database.database import init_db; init_db()\"")
        
    print("\n✓ PostgreSQL is ready!")
    print("\nYou can now start the backend:")
    print("  uvicorn backend.main:app --reload")
    
except Exception as e:
    print(f"\n❌ PostgreSQL connection failed!")
    print(f"   Error: {e}")
    print("\nTroubleshooting steps:")
    print("1. Check if PostgreSQL is running:")
    print("   • Windows: services.msc → PostgreSQL service")
    print("   • Linux: sudo systemctl status postgresql")
    print("   • Mac: brew services list")
    print("\n2. Verify database exists:")
    print("   psql -U postgres")
    print("   CREATE DATABASE trace;")
    print("   \\q")
    print("\n3. Check DATABASE_URL format:")
    print("   postgresql://username:password@localhost:5432/trace")
    print("\n4. Verify credentials:")
    print("   • Username matches PostgreSQL user")
    print("   • Password is correct (or empty if no password)")
    print("   • Port 5432 is correct (default PostgreSQL port)")
    
    sys.exit(1)
