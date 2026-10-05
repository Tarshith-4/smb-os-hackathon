import os
import tempfile

_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_dir}/test.db"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("API_KEY", None)
os.environ.pop("SMTP_HOST", None)

import pytest  # noqa: E402

from backend.database import Base, SessionLocal, engine  # noqa: E402
from backend.seed import ensure_demo_threat, seed_database  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_database(session)
        ensure_demo_threat(session)
        yield session
