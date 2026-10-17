from __future__ import annotations

from starlette.requests import Request

from backend import main


def _request(path: str, host: str = "198.51.100.10") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "client": (host, 1234),
            "server": ("test", 8000),
            "scheme": "http",
        }
    )


def test_rate_rule_matches_chat_and_search_prefixes():
    assert main._rate_rule("/api/search/v2")[0] == "/api/search"
    assert main._rate_rule("/api/chat/message")[0] == "/api/chat"
    assert main._rate_rule("/api/news") is None


def test_rate_limiter_uses_client_address_and_returns_429(monkeypatch):
    original = main._RATE_RULES["/api/search"]
    original_buckets = main._rate_buckets
    main._RATE_RULES["/api/search"] = (2, 60)
    main._rate_buckets.clear()

    async def call_next(request):
        from starlette.responses import Response

        return Response(status_code=204)

    try:
        import asyncio

        assert asyncio.run(main._rate_limit(_request("/api/search"), call_next)).status_code == 204
        assert asyncio.run(main._rate_limit(_request("/api/search"), call_next)).status_code == 204
        assert asyncio.run(main._rate_limit(_request("/api/search"), call_next)).status_code == 429
        assert asyncio.run(main._rate_limit(_request("/api/search", "198.51.100.11"), call_next)).status_code == 204
    finally:
        main._RATE_RULES["/api/search"] = original
        main._rate_buckets.clear()
