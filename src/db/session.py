from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import get_settings

engine = create_engine(settings.MYSQL_CONN, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
