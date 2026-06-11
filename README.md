# API Gateway

Central entry point for all client traffic. Validates Keycloak JWTs and reverse-proxies requests to downstream services with trusted user context headers.

## What It Does

1. **Authenticates** every request by validating the JWT against Keycloak's JWKS endpoint
2. **Resolves** the target service using config-driven route matching (longest prefix wins)
3. **Strips** client-supplied identity headers (`X-User-Id`, `X-User-Roles`, `X-User-Email`) to prevent spoofing
4. **Injects** trusted headers from the validated JWT claims before forwarding
5. **Proxies** the request to the downstream service and returns the response as-is

The gateway does **not** enforce RBAC — that's the responsibility of each service via the shared auth libraries.

## Request Flow

```
Client --[JWT]--> Gateway --[validates token]--> Route resolution
                                                      |
                                          Strip spoofable headers
                                          Inject X-User-Id, X-User-Roles, X-User-Email, X-Request-Id
                                                      |
                                              Downstream service
```

## Setup

```bash
cp .env.example .env   # edit values as needed
poetry install
poetry run uvicorn app.main:app --port 8000 --reload
```

Requires a running Keycloak instance — see `infra/docker/docker-compose.yaml`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `KEYCLOAK_ISSUER_URL` | Yes | Keycloak realm URL (e.g. `http://localhost:8080/realms/dls`) |
| `KEYCLOAK_AUDIENCE` | Yes | Keycloak client ID (e.g. `dls-gateway`) |
| `PROXY_TIMEOUT_SECONDS` | No | Upstream timeout, default 30s |
| `ORDER_SERVICE_BASE_URL` | No | e.g. `http://localhost:8001` |
| `RESTAURANT_SERVICE_BASE_URL` | No | e.g. `http://localhost:8082` |
| `COURIER_SERVICE_BASE_URL` | No | e.g. `http://localhost:8083` |
| `PAYMENT_SERVICE_BASE_URL` | No | e.g. `http://localhost:8084` |
| `NOTIFICATION_SERVICE_BASE_URL` | No | e.g. `http://localhost:8085` |
| `USER_SERVICE_BASE_URL` | No | e.g. `http://localhost:8086` |

## Route Configuration

Default routes are built in for all services:

| Prefix | Target |
|--------|--------|
| `/api/v1/orders` | `ORDER_SERVICE_BASE_URL` |
| `/api/v1/restaurants` | `RESTAURANT_SERVICE_BASE_URL` |
| `/api/v2/couriers` | `COURIER_SERVICE_BASE_URL` |
| `/api/v2/deliveries` | `COURIER_SERVICE_BASE_URL` |
| `/api/v1/payments` | `PAYMENT_SERVICE_BASE_URL` |
| `/api/v1/notifications` | `NOTIFICATION_SERVICE_BASE_URL` |
| `/api/v1/users` | `USER_SERVICE_BASE_URL` |
| `/graphql` | `USER_SERVICE_BASE_URL` |

Matching is prefix-based, so `/api/v1/orders/123` and `PATCH /api/v1/orders/123` both route to the order service. The full path is forwarded as-is.

All downstream services should expose their endpoints under `/api/v1/...` to match.

## Forwarded Headers

The gateway rebuilds these headers from the validated JWT before forwarding:

| Header | Source |
|--------|--------|
| `X-User-Id` | JWT `sub` claim |
| `X-User-Roles` | JWT `realm_access.roles`, comma-separated |
| `X-User-Email` | JWT `email` claim |
| `X-Request-Id` | Generated per request by `RequestContextMiddleware` |

## Error Responses

| Status | When |
|--------|------|
| 401 | Missing or invalid JWT |
| 404 | Path matches no configured route |
| 502 | Downstream service unreachable |
| 504 | Downstream service timed out |

## Tests

```bash
poetry run pytest -v                       # unit tests (53 tests)
poetry run pytest tests/integration/ -v    # integration tests (requires running Keycloak)
```

Integration tests skip automatically if Keycloak is not available.
