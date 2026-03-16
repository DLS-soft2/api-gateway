import os

os.environ.setdefault("KEYCLOAK_ISSUER_URL", "http://localhost:8080/realms/dls")
os.environ.setdefault("KEYCLOAK_AUDIENCE", "dls-gateway")
os.environ.setdefault("USER_SERVICE_BASE_URL", "http://localhost:8001")
