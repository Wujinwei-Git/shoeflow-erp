from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def create_database_engine() -> Engine:
    """创建数据库引擎。"""

    connect_args: dict[str, object] = {}
    engine_options: dict[str, object] = {}

    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

        if ":memory:" in settings.database_url:
            engine_options["poolclass"] = StaticPool

    return create_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        connect_args=connect_args,
        **engine_options,
    )


engine = create_database_engine()

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 数据库会话依赖。"""

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()