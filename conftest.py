import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.database import Base, get_db
from src.main import app

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Creates a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)  # Create tables
    
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    # Use our test database instead of the standard one
    def override_get_db():
        try:
            yield session
            session.commit()
        finally:
            session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield session  # The test will run here
    
    # Teardown
    transaction.rollback()
    connection.close()
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(db_session):
    """Creates a FastAPI TestClient with database session fixture."""
    with TestClient(app) as test_client:
        yield test_client 