from __future__ import annotations

import ipaddress
import re
import secrets
from urllib.parse import parse_qs

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from worldbuilder_core.config import Settings


class RequestBodyTooLargeError(Exception):
    pass


class ApplicationSecurityMiddleware:
    """Protect Master APIs, cap request bodies, and add browser security headers."""

    _public_player_reads = (
        re.compile(r"^/worlds/[^/]+/(?:entities|relationships|world-rules|map-pins|random-tables|detective-board|context|entity-types|quest-statuses)/?$").fullmatch,
        re.compile(r"^/(?:entities|relationships|world-rules|map-pins|random-tables)/[^/]+/?$").fullmatch,
    )
    _public_world_read = re.compile(r"^/worlds(?:/[^/]+)?/?$").fullmatch
    _public_player_roll = re.compile(r"^/random-tables/[^/]+/roll/?$").fullmatch

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.api_prefix = f"/{settings.api_prefix.strip('/')}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        response_started = False

        async def secure_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                self._add_security_headers(message, path=path, scheme=scope.get("scheme", "http"))
            await send(message)

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        body_limit = self._body_limit(scope)
        if not self._has_allowed_host(headers):
            await self._reject(scope, receive, secure_send, 400, "Invalid Host header")
            return

        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > body_limit:
                    await self._reject(scope, receive, secure_send, 413, "Request body is too large")
                    return
            except ValueError:
                await self._reject(scope, receive, secure_send, 400, "Invalid Content-Length header")
                return

        if self._requires_master(scope) and not self._has_master_access(scope, headers):
            await self._reject(scope, receive, secure_send, 403, "Master access denied")
            return

        received_bytes = 0

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > body_limit:
                    raise RequestBodyTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, secure_send)
        except RequestBodyTooLargeError:
            if response_started:
                raise
            await self._reject(scope, receive, secure_send, 413, "Request body is too large")

    def _body_limit(self, scope: Scope) -> int:
        path = scope.get("path", "")
        relative_path = path.removeprefix(self.api_prefix)
        is_document_upload = (
            scope.get("method", "GET").upper() == "POST"
            and re.fullmatch(r"/worlds/[^/]+/documents/?", relative_path) is not None
        )
        return self.settings.max_document_bytes if is_document_upload else self.settings.max_request_bytes

    def _requires_master(self, scope: Scope) -> bool:
        path = scope.get("path", "")
        if not path.startswith(self.api_prefix):
            return False

        relative_path = path[len(self.api_prefix) :] or "/"
        method = scope.get("method", "GET").upper()
        if method == "OPTIONS":
            return False
        if method in {"GET", "HEAD"} and self._public_world_read(relative_path):
            return False

        query = parse_qs(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
        role = query.get("role", [""])[-1]
        if role == "player":
            if method in {"GET", "HEAD"} and any(match(relative_path) for match in self._public_player_reads):
                return False
            if method == "POST" and self._public_player_roll(relative_path):
                return False
        return True

    def _has_master_access(self, scope: Scope, headers: dict[bytes, bytes]) -> bool:
        client = scope.get("client")
        host = client[0] if client else ""
        if self.settings.trust_local_master and _is_loopback_host(host):
            return True

        expected = self.settings.master_token
        provided = headers.get(b"x-worldbuilder-master-token", b"").decode("utf-8", errors="ignore")
        return bool(expected and provided and secrets.compare_digest(provided, expected))

    def _has_allowed_host(self, headers: dict[bytes, bytes]) -> bool:
        value = headers.get(b"host", b"").decode("latin-1").strip()
        host = _host_without_port(value)
        if not host:
            return False
        if host in self.settings.allowed_hosts:
            return True
        try:
            ipaddress.ip_address(host.split("%", 1)[0])
            return True
        except ValueError:
            return False

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        status_code: int,
        detail: str,
    ) -> None:
        response = JSONResponse({"detail": detail}, status_code=status_code)
        await response(scope, receive, send)

    @staticmethod
    def _add_security_headers(message: Message, *, path: str, scheme: str) -> None:
        headers = list(message.get("headers", []))
        existing = {key.lower() for key, _ in headers}
        additions = {
            b"x-content-type-options": b"nosniff",
            b"referrer-policy": b"no-referrer",
            b"x-frame-options": b"DENY",
            b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
        }
        if path == "/app" or path.startswith("/app/"):
            additions[b"cache-control"] = b"no-store"
            additions[b"content-security-policy"] = (
                b"default-src 'self'; img-src 'self' data: http: https:; "
                b"script-src 'self'; style-src 'self' 'unsafe-inline'; "
                b"connect-src 'self'; object-src 'none'; base-uri 'self'; "
                b"frame-ancestors 'none'; form-action 'self'"
            )
        if scheme == "https":
            additions[b"strict-transport-security"] = b"max-age=31536000"
        headers.extend((key, value) for key, value in additions.items() if key not in existing)
        message["headers"] = headers


def _is_loopback_host(value: str) -> bool:
    host = value.split("%", 1)[0].strip().lower()
    if host in {"localhost", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _host_without_port(value: str) -> str:
    host = value.strip().lower()
    if host.startswith("["):
        closing_bracket = host.find("]")
        return host[1:closing_bracket].rstrip(".") if closing_bracket > 0 else ""
    if host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host.rstrip(".")
