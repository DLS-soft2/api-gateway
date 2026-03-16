from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.middleware.request_context import RequestContextMiddleware, REQUEST_ID_HEADER


def _create_test_app():
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/context")
    def read_context(request: Request):
        return {"request_id": request.state.request_id}

    return app


def test_preserves_inbound_request_id():
    client = TestClient(_create_test_app())
    response = client.get("/context", headers={REQUEST_ID_HEADER: "external-id"})

    assert response.status_code == 200
    assert response.json()["request_id"] == "external-id"
    assert response.headers[REQUEST_ID_HEADER] == "external-id"


def test_generates_request_id_when_missing():
    client = TestClient(_create_test_app())
    response = client.get("/context")

    request_id = response.json()["request_id"]
    assert request_id
    assert response.headers[REQUEST_ID_HEADER] == request_id
