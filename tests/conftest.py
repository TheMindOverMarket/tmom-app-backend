import pytest
import uuid
import os
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Set fake Alpaca environment variables for tests
os.environ["ALPACA_API_KEY"] = "fake_key"
os.environ["ALPACA_API_SECRET"] = "fake_secret"
os.environ["DATABASE_URL"] = "sqlite://"

from app.main import app
from app.config import settings
from app.database import get_session
from app.models import User

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"

@pytest.fixture(name="db_session", scope="function")
def session_fixture():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(db_session: Session):
    def get_session_override():
        return db_session
    
    app.dependency_overrides[get_session] = get_session_override
    previous_run_db_migrations = settings.run_db_migrations_on_startup
    settings.run_db_migrations_on_startup = False
    app.state.schema_status = "ready"
    app.state.schema_error = None
    
    # Mock lifecycle to avoid real WebSockets/background tasks
    with patch("app.main.on_startup", new_callable=AsyncMock), \
         patch("app.main.on_shutdown", new_callable=AsyncMock):
        with TestClient(app) as client:
            client.app.state.schema_status = "ready"
            client.app.state.schema_error = None
            yield client
            
    settings.run_db_migrations_on_startup = previous_run_db_migrations
    app.dependency_overrides.clear()

@pytest.fixture(name="test_user")
def test_user_fixture(db_session: Session):
    user = User(email="demo@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
