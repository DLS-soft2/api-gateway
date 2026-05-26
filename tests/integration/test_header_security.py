import pytest


@pytest.mark.asyncio
async def test_spoofed_x_user_id_is_stripped(client, customer_token, upstream_mock):
    """Client-supplied X-User-Id is replaced with the Keycloak token's sub claim."""
    await client.get(
        "/api/orders/1",
        headers={
            "Authorization": f"Bearer {customer_token}",
            "X-User-Id": "attacker-spoofed-id",
        },
    )
    assert len(upstream_mock.captured) == 1
    forwarded = upstream_mock.last_request["headers"]
    assert forwarded["x-user-id"] != "attacker-spoofed-id"
    assert len(forwarded["x-user-id"]) > 0


@pytest.mark.asyncio
async def test_x_user_roles_from_keycloak_token(client, customer_token, upstream_mock):
    """X-User-Roles header comes from the Keycloak token, not the client."""
    await client.get(
        "/api/orders/1",
        headers={
            "Authorization": f"Bearer {customer_token}",
            "X-User-Roles": "superadmin,root",
        },
    )
    assert len(upstream_mock.captured) == 1
    forwarded = upstream_mock.last_request["headers"]
    roles = forwarded["x-user-roles"].split(",")
    assert "customer" in roles
    assert "superadmin" not in roles
    assert "root" not in roles


@pytest.mark.asyncio
async def test_x_request_id_forwarded(client, customer_token, upstream_mock):
    """X-Request-Id from the client is preserved and forwarded to upstream."""
    custom_request_id = "req-integration-test-abc"
    await client.get(
        "/api/orders/1",
        headers={
            "Authorization": f"Bearer {customer_token}",
            "X-Request-Id": custom_request_id,
        },
    )
    assert len(upstream_mock.captured) == 1
    forwarded = upstream_mock.last_request["headers"]
    assert forwarded["x-request-id"] == custom_request_id


@pytest.mark.asyncio
async def test_different_role_token(client, courier_token, upstream_mock):
    """Courier token produces X-User-Roles containing 'courier'."""
    await client.get(
        "/api/orders/1",
        headers={"Authorization": f"Bearer {courier_token}"},
    )
    assert len(upstream_mock.captured) == 1
    forwarded = upstream_mock.last_request["headers"]
    roles = forwarded["x-user-roles"].split(",")
    assert "courier" in roles
