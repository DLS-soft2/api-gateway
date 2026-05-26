import os

os.environ.setdefault("KEYCLOAK_ISSUER_URL", "http://localhost:8080/realms/dls")
os.environ.setdefault("KEYCLOAK_AUDIENCE", "dls-gateway")
os.environ.setdefault("ORDER_SERVICE_BASE_URL", "http://localhost:8002")
os.environ.setdefault("RESTAURANT_SERVICE_BASE_URL", "http://localhost:8003")
os.environ.setdefault("COURIER_SERVICE_BASE_URL", "http://localhost:8004")
os.environ.setdefault("PAYMENT_SERVICE_BASE_URL", "http://localhost:8005")
os.environ.setdefault("NOTIFICATION_SERVICE_BASE_URL", "http://localhost:8006")
os.environ.setdefault("USER_SERVICE_BASE_URL", "http://localhost:8001")
