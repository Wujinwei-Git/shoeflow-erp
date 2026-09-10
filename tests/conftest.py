import os

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+pysqlite:///:memory:",
)
os.environ.setdefault(
    "ENVIRONMENT",
    "test",
)
os.environ.setdefault(
    "DEBUG",
    "false",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-" + "0" * 52,
)

import pytest

import app.models
from app.db.base import Base
from app.db.session import engine


@pytest.fixture(autouse=True)
def clean_database():
    """每个测试开始前创建表，结束后清理表。"""

    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)