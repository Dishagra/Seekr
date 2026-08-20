import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rip.db import Base
from rip import models  # noqa: F401


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        yield s
