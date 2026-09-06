"""End-to-end HTTP test for web search chat."""

from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def post(path: str, body: dict, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def get(path: str, token: str) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, json.loads(resp.read().decode())


def main() -> None:
    _, login = post("/api/v1/auth/login", {"email": "demo@example.com", "password": "demo12345"})
    token = login["access_token"]

    status, health = get("/api/v1/admin/web-search/health", token)
    print("HEALTH", status, health)

    status, test = post(
        "/api/v1/admin/web-search/test",
        {"query": "Leopards Pakistan courier services"},
        token,
    )
    print("TEST", status, {k: test.get(k) for k in ("success", "result_count", "error_code")})

    msg = "Search the web and tell me the latest information about Leopards' relevant shipping services."
    status, chat = post(
        "/api/v1/ai/chat",
        {
            "message": msg,
            "conversation_id": None,
            "shipment_id": None,
            "preferences": {"priority": "balanced"},
        },
        token,
    )
    print("CHAT", status)
    print(
        json.dumps(
            {
                "rag_used": chat.get("rag_used"),
                "web_search_used": chat.get("web_search_used"),
                "llm_success": chat.get("llm_success"),
                "web_search_error_code": chat.get("web_search_error_code"),
                "internal_error_codes": chat.get("internal_error_codes"),
                "data_source": chat.get("data_source"),
                "source_count": len(chat.get("sources", [])),
                "answer_preview": (chat.get("answer") or "")[:200],
            },
            indent=2,
        )
    )
    if status != 200:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
