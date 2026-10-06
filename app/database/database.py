from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


DATABASE_URL = settings.DATABASE_URL

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }


engine_kwargs = {
    "connect_args": connect_args,
}

if DATABASE_URL.startswith(("postgresql://", "postgresql+")):
    engine_kwargs.update(
        {
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
            "pool_recycle": settings.DATABASE_POOL_RECYCLE,
            "pool_pre_ping": settings.DATABASE_POOL_PRE_PING,
        }
    )

engine = create_engine(
    DATABASE_URL,
    **engine_kwargs,
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
