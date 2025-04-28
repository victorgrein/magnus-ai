from src.config.settings import settings
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.sessions import DatabaseSessionService
from google.adk.memory import InMemoryMemoryService

# Initialize service instances
session_service = DatabaseSessionService(db_url=settings.POSTGRES_CONNECTION_STRING)
artifacts_service = InMemoryArtifactService()
memory_service = InMemoryMemoryService()
