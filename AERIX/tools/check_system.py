"""
Complete system check for TRACE backend
Checks all prerequisites and provides actionable guidance
"""

import sys
import os
from pathlib import Path
import subprocess

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("TRACE System Check")
print("=" * 70)

# Test 1: Python version
print("\n[1/7] Python Version")
python_version = sys.version_info
print(f"  Python {python_version.major}.{python_version.minor}.{python_version.micro}")
if python_version.major >= 3 and python_version.minor >= 10:
    print("  ✓ Python version is compatible")
else:
    print("  ⚠ Warning: Python 3.10+ recommended")

# Test 2: Environment file
print("\n[2/7] Environment File")
env_file = project_root / ".env"
if env_file.exists():
    print(f"  ✓ .env file found at {env_file}")
    
    # Load and check DATABASE_URL
    from dotenv import load_dotenv
    load_dotenv(env_file)
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # Mask password
        if "://" in database_url:
            scheme, rest = database_url.split("://", 1)
            if "@" in rest:
                creds, host = rest.split("@", 1)
                if ":" in creds:
                    user, _ = creds.split(":", 1)
                    masked = f"{scheme}://{user}:****@{host}"
                else:
                    masked = database_url
            else:
                masked = database_url
        else:
            masked = database_url
        print(f"  ✓ DATABASE_URL: {masked}")
    else:
        print("  ❌ DATABASE_URL not found in .env")
else:
    print(f"  ❌ .env file not found at {env_file}")
    print("  Create .env with:")
    print("  DATABASE_URL=postgresql://postgres@localhost:5432/trace")

# Test 3: PostgreSQL Service (Windows)
print("\n[3/7] PostgreSQL Service")
try:
    result = subprocess.run(
        ["powershell", "-Command", "Get-Service -Name 'postgresql*' | Select-Object Name, Status"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.returncode == 0 and result.stdout.strip():
        print("  PostgreSQL services found:")
        for line in result.stdout.strip().split('\n')[2:]:  # Skip header
            if line.strip():
                print(f"    {line.strip()}")
        
        # Check if any are running
        if "Running" in result.stdout:
            print("  ✓ PostgreSQL service is running")
        else:
            print("  ❌ PostgreSQL service is stopped")
            print("  Fix: Start-Service postgresql-x64-14")
    else:
        print("  ⚠ No PostgreSQL service found")
        print("  Options:")
        print("    1. Install PostgreSQL from postgresql.org")
        print("    2. Use Docker: docker run -d -p 5432:5432 postgres:14")
except Exception as e:
    print(f"  ⚠ Could not check service: {e}")

# Test 4: Port 5432 (PostgreSQL)
print("\n[4/7] PostgreSQL Port")
try:
    result = subprocess.run(
        ["powershell", "-Command", "Test-NetConnection -ComputerName localhost -Port 5432 -WarningAction SilentlyContinue | Select-Object TcpTestSucceeded"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if "True" in result.stdout:
        print("  ✓ Port 5432 is open (PostgreSQL is listening)")
    else:
        print("  ❌ Port 5432 is closed (PostgreSQL is not listening)")
        print("  Fix: Start PostgreSQL service")
except Exception as e:
    print(f"  ⚠ Could not check port: {e}")

# Test 5: Database connection
print("\n[5/7] Database Connection")
try:
    from sqlalchemy import create_engine, text
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"  ✓ Connected to PostgreSQL")
            print(f"    {version.split(',')[0]}")
    else:
        print("  ❌ DATABASE_URL not set")
except Exception as e:
    print(f"  ❌ Connection failed: {str(e).split(chr(10))[0]}")
    print("  Troubleshooting:")
    print("    1. Ensure PostgreSQL is running")
    print("    2. Check DATABASE_URL in .env")
    print("    3. Verify database 'trace' exists")

# Test 6: Backend dependencies
print("\n[6/7] Backend Dependencies")
missing_deps = []
for package in ["fastapi", "uvicorn", "sqlalchemy", "psycopg2", "python-dotenv"]:
    try:
        __import__(package.replace("-", "_"))
        print(f"  ✓ {package}")
    except ImportError:
        print(f"  ❌ {package}")
        missing_deps.append(package)

if missing_deps:
    print(f"\n  Install missing: pip install {' '.join(missing_deps)}")

# Test 7: Configuration imports
print("\n[7/7] Backend Configuration")
try:
    from backend.core.config import settings
    print("  ✓ Configuration loaded")
    print(f"    Project root: {settings.PROJECT_ROOT}")
    print(f"    Upload dir: {settings.UPLOAD_DIR}")
    print(f"    Video dir: {settings.VIDEO_DIR}")
except Exception as e:
    print(f"  ❌ Configuration failed: {e}")

# Summary
print("\n" + "=" * 70)
print("Summary")
print("=" * 70)

# Determine what's blocking
blocking_issues = []

# Check PostgreSQL
try:
    result = subprocess.run(
        ["powershell", "-Command", "Test-NetConnection -ComputerName localhost -Port 5432 -WarningAction SilentlyContinue | Select-Object TcpTestSucceeded"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if "True" not in result.stdout:
        blocking_issues.append("PostgreSQL not running")
except:
    blocking_issues.append("PostgreSQL status unknown")

# Check database connection
try:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
except:
    if "PostgreSQL not running" not in blocking_issues:
        blocking_issues.append("Database connection failed")

if not blocking_issues:
    print("\n✓ All checks passed! You can start the backend:")
    print("\n  uvicorn backend.main:app --reload")
    print("\nOr test first:")
    print("  python test_startup.py")
    print("  python check_postgres.py")
else:
    print("\n❌ Issues found:")
    for i, issue in enumerate(blocking_issues, 1):
        print(f"  {i}. {issue}")
    
    print("\nRecommended steps:")
    if "PostgreSQL not running" in blocking_issues:
        print("\n1. Start PostgreSQL:")
        print("   Start-Service postgresql-x64-14")
        print("   OR install from: https://www.postgresql.org/download/")
        print("   OR use Docker: docker run -d -p 5432:5432 postgres:14")
        
        print("\n2. Create database:")
        print("   psql -U postgres")
        print("   CREATE DATABASE trace;")
        print("   \\q")
        
        print("\n3. Verify:")
        print("   python check_postgres.py")
        
        print("\n4. Start backend:")
        print("   uvicorn backend.main:app --reload")
    
    print("\nFor detailed help:")
    print("  See START_POSTGRES.md")

print("")
