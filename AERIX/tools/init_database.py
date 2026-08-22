"""
Initialize database tables
Run this after PostgreSQL is confirmed to be working
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("TRACE Database Initialization")
print("=" * 60)

# Step 1: Load configuration
print("\n[Step 1] Loading configuration...")
try:
    from backend.core.config import settings
    print("✓ Configuration loaded")
except Exception as e:
    print(f"❌ Configuration failed: {e}")
    sys.exit(1)

# Step 2: Test connection
print("\n[Step 2] Testing database connection...")
try:
    from database.database import test_connection
    test_connection()
except Exception as e:
    print(f"❌ Connection test failed: {e}")
    print("\nMake sure:")
    print("1. PostgreSQL is running")
    print("2. Database 'trace' exists")
    print("3. DATABASE_URL in .env is correct")
    sys.exit(1)

# Step 3: Initialize tables
print("\n[Step 3] Creating database tables...")
try:
    from database.database import init_db
    init_db()
except Exception as e:
    print(f"❌ Table creation failed: {e}")
    sys.exit(1)

# Step 4: Run seed data (if exists)
print("\n[Step 4] Checking for seed data...")
seed_sql = project_root / "database" / "seed.sql"
if seed_sql.exists():
    print(f"✓ Found seed.sql at {seed_sql}")
    print("  To apply seed data, run:")
    print(f'  psql -U postgres -d trace -f "{seed_sql}"')
else:
    print("  No seed.sql found")

# Success
print("\n" + "=" * 60)
print("✓ Database initialized successfully!")
print("=" * 60)
print("\nYou can now start the backend:")
print("  uvicorn backend.main:app --reload")
