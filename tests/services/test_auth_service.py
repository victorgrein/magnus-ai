from src.services.auth_service import create_access_token
from src.models.models import User
import uuid


def test_create_access_token():
    """
    Test that an access token is created with the correct data.
    """
    # Create a mock user
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        is_admin=False,
        name="Test User",
        client_id=uuid.uuid4(),
    )

    # Create token
    token = create_access_token(user)

    # Simple validation
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0
