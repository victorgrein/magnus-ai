def test_read_root(client):
    """
    Test that the root endpoint returns the correct response.
    """
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "documentation" in data
    assert "version" in data
    assert "auth" in data
