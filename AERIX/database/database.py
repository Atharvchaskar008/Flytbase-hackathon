import sys
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend.core.logger import logger
from database.base import Base
from database.session import engine


def init_db() -> None:
    """Initialize database tables"""
    try:
        # Import all models to register them with Base
        import database.models  # noqa: F401
        
        # Test connection first
        print("→ Testing database connection...")
        test_connection()
        
        # Create all tables
        print("→ Creating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables initialized")
        logger.info("Database tables initialized")
        
    except OperationalError as e:
        print(f"\n❌ PostgreSQL connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if PostgreSQL is running:")
        print("   Windows: services.msc → PostgreSQL")
        print("   Linux: sudo systemctl status postgresql")
        print("2. Verify database 'trace' exists:")
        print("   psql -U postgres")
        print("   CREATE DATABASE trace;")
        print("3. Check DATABASE_URL in .env")
        print("4. Verify username/password are correct")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


def test_connection() -> str:
    """Test database connection"""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        message = "Connected to PostgreSQL"
        print(f"✓ {message}")
        logger.info(message)
        return message
    except OperationalError as e:
        error_msg = f"PostgreSQL connection failed: {e}"
        print(f"\n❌ {error_msg}")
        print("\nCommon issues:")
        print("• PostgreSQL service not running")
        print("• Wrong host/port in DATABASE_URL")
        print("• Database 'trace' does not exist")
        print("• Invalid credentials")
        raise
    except Exception as e:
        error_msg = f"Database connection test failed: {e}"
        print(f"\n❌ {error_msg}")
        logger.error(error_msg)
        raise
