from collections.abc import Generator
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings

# Create engine with connection pool settings
try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=settings.DEBUG,
    )
    print("[OK] SQLAlchemy engine created")
except Exception as e:
    print(f"\n[ERROR] Failed to create database engine: {e}")
    print("\nTroubleshooting steps:")
    print("1. Check if PostgreSQL is running")
    print("2. Verify DATABASE_URL in .env file")
    print("3. Ensure database 'trace' exists")
    print("4. Check username and password")
    sys.exit(1)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
