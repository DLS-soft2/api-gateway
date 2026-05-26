import pytest


@pytest.mark.asyncio
async def test_spoofed_x_user_id_is_stripped(client, token_factory, upstream_mock):
    """Client-supplied X-User-Id is replaced with the JWT's sub claim."""
    token = token_factory({"sub": "real-user-42"})
    await client.get(
        "/api/orders/1",
        headers={
            "Authorization": f"Bearer {token}",
            "X-User-Id": "attacker-spoofed-id",
        },
    )
    assert len(upstream_mock.captured) == 1
    forwarded = upstream_mock.last_request.headers
    assert forwarded["x-user-id"] == "real-user-42"


@pytest.mark.asyncio
async def test_x_user_roles_from_jwt_not_client(client, token_factory, upstream_mock):
    """Client-supplied X-User-Roles is replaced with roles from the JWT."""
    token = token_factory({"realm_access": {"roles": ["courier", "admin"]}})
    await client.get(
        "/api/orders/1",
        headers={
            "Authorization": f"Bearer {token}",
            "X-User-Roles": "superadmin,root",
        },
    )
    assert len(upstream_mock.captured) == 1
    forwarded = upstream_mock.last_request.headers
    roles = forwarded["x-user-roles"].split(",")
    assert "courier" in roles
    assert "admin" in roles
    assert "superadmin" not in roles
    assert "root" not in roles


@pytest.mark.asyncio
async def test_x_request_id_forwarded(client, token_factory, upstream_mock):
    """X-Request-Id from the client is preserved through the middleware and forwarded."""
    token = token_factory()
    custom_request_id = "req-integration-test-abc"
    await client.get(
        "/api/orders/1",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-Id": custom_request_id,
        },
    )
    assert len(upstream_mock.captured) == 1
    forwarded = upstream_mock.last_request.headers
    assert forwarded["x-request-id"] == custom_request_id


@pytest.mark.asyncio
async def test_x_user_email_from_jwt(client, token_factory, upstream_mock):
    """X-User-Email header is set from the JWT email claim, not client-supplied."""
    token = token_factory({"email": "real@example.com"})
    await client.get(
        "/api/orders/1",
        headers={
            "Authorization": f"Bearer {token}",
            "X-User-Email": "evil@hacker.com",
        },
    )
    assert len(upstream_mock.captured) == 1
    forwarded = upstream_mock.last_request.headers
    assert forwarded["x-user-email"] == "real@example.com"
