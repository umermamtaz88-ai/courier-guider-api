"""Auth and chat endpoint authorization tests."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.security.auth import create_access_token

settings = get_settings()
client = TestClient(app)


def _chat_payload(message: str = "hello") -> dict:
    return {
        "message": message,
        "conversation_id": None,
        "shipment_id": None,
        "preferences": {"priority": "balanced"},
    }


def test_chat_without_token_returns_structured_auth_error():
    response = client.post("/api/v1/ai/chat", json=_chat_payload())
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert body["error"]["message"]
    assert body["error"]["request_id"]
    assert "CURRENT_DATA_UNAVAILABLE" not in body["error"]["code"]


def test_chat_with_invalid_token_returns_structured_error():
    response = client.post(
        "/api/v1/ai/chat",
        json=_chat_payload(),
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] in {"INVALID_TOKEN", "AUTHENTICATION_REQUIRED"}
    assert body["error"]["request_id"]


def test_chat_with_expired_token_returns_session_expired():
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
            "type": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = client.post(
        "/api/v1/ai/chat",
        json=_chat_payload(),
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


def test_chat_with_valid_token_but_missing_tenant_returns_tenant_required():
    token = create_access_token(str(uuid.uuid4()))
    response = client.post(
        "/api/v1/ai/chat",
        json=_chat_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in (400, 401)
    body = response.json()
    assert body["error"]["code"] in {"TENANT_REQUIRED", "USER_NOT_FOUND", "INVALID_TOKEN"}


def test_login_and_chat_success():
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@example.com", "password": "demo12345", "tenant_id": None},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    chat = client.post(
        "/api/v1/ai/chat",
        json=_chat_payload("What is COD?"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert chat.status_code == 200, chat.text
    body = chat.json()
    assert body.get("answer")
    assert body.get("conversation_id")


def test_provider_comparison_authenticated():
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@example.com", "password": "demo12345", "tenant_id": None},
    )
    token = login.json()["access_token"]
    chat = client.post(
        "/api/v1/ai/chat",
        json=_chat_payload(
            "I have 8kg clothes from Lahore to Karachi. Which courier is better?"
        ),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert chat.status_code == 200, chat.text
    body = chat.json()
    assert body.get("answer")
    assert body.get("rag_used") is True
