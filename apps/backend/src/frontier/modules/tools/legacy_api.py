import asyncio
import ipaddress
import socket
import time
from typing import Literal
from urllib.parse import urljoin, urlsplit

import httpx
from langchain.tools import ToolRuntime

from frontier.clients.secrets import SecretsClient
from frontier.contracts.secrets import ResolveSecretRequest
from frontier.contracts.tools import MigrationRunContext
from frontier.modules.tools.errors import HostOutsideScopeError, NonPublicHostError
from frontier.modules.tools.redaction import redact_for_run
from frontier.modules.tools.schemas import PathReport

PROBE_CONCURRENCY = 4
MAX_BODY_CHARS = 20_000
MILLISECONDS_PER_SECOND = 1000
NOT_FOUND_STATUS = 404
MISSING_CONTENT_TYPE = "-"
DOCUMENTATION_PATHS = (
    "/",
    "/openapi.json",
    "/swagger.json",
    "/docs",
    "/redoc",
    "/health",
    "/healthz",
    "/status",
    "/version",
    "/api",
    "/v1",
)

HttpMethod = Literal["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"]
AuthMode = Literal["none", "bearer", "header", "query"]
CALLER_FORBIDDEN_HEADERS = frozenset({"host"})


class LegacyApiProbe:
    """HTTP access to the legacy API, scoped to the job's base URL, with server-side auth."""

    def __init__(self, *, secrets: SecretsClient, timeout_s: float) -> None:
        self._secrets = secrets
        self._timeout_s = timeout_s
        self._concurrency = asyncio.Semaphore(PROBE_CONCURRENCY)

    async def discover_endpoints(self, runtime: ToolRuntime[MigrationRunContext]) -> str:
        """Request the API's documentation and health paths (e.g. /openapi.json, /docs, /health)
        without credentials and report which exist, as `path status content-type bytes`."""
        context = runtime.context
        try:
            await _ensure_public_host(context.base_url)
        except (NonPublicHostError, socket.gaierror) as error:
            return await redact_for_run(self._secrets, f"rejected: {error}", context)
        async with httpx.AsyncClient(timeout=self._timeout_s, follow_redirects=False) as client:
            path_reports = await asyncio.gather(
                *(
                    self._fetch_unauthenticated(client, context, path)
                    for path in DOCUMENTATION_PATHS
                )
            )
        existing_first = sorted(path_reports, key=lambda path_report: not path_report.exists)
        report = "\n".join(path_report.line for path_report in existing_first)
        return await redact_for_run(self._secrets, report, context)

    async def probe_http(
        self,
        method: HttpMethod,
        path: str,
        runtime: ToolRuntime[MigrationRunContext],
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict | list | None = None,
        text_body: str | None = None,
        auth: AuthMode = "none",
        auth_header_name: str = "Authorization",
    ) -> str:
        """Send one HTTP request to the legacy API and return status, headers, body and latency.

        `path` is relative to the API base URL. Redirects are not followed. `auth` attaches the
        service credential server-side: `bearer` sets `Authorization: Bearer <key>`, `header`
        sets `<auth_header_name>: <key>`, `query` adds `<auth_header_name>=<key>` to the query.
        """
        context = runtime.context
        request_query = dict(query or {})
        request_headers = {
            name: value
            for name, value in (headers or {}).items()
            if name.lower() not in CALLER_FORBIDDEN_HEADERS
        }
        try:
            url = _scoped_url(context.base_url, path)
            await _ensure_public_host(url)
            await self._attach_auth(context, auth, auth_header_name, request_headers, request_query)
            report = await self._send(
                method, url, request_query, request_headers, json_body, text_body
            )
        except (HostOutsideScopeError, NonPublicHostError) as error:
            report = f"rejected: {error}"
        except (httpx.HTTPError, socket.gaierror) as error:
            report = f"request_failed: {type(error).__name__}: {error}"
        return await redact_for_run(self._secrets, report, context)

    async def _fetch_unauthenticated(
        self, client: httpx.AsyncClient, context: MigrationRunContext, path: str
    ) -> PathReport:
        url = _scoped_url(context.base_url, path)
        async with self._concurrency:
            try:
                response = await client.get(url)
            except httpx.HTTPError as error:
                return PathReport(
                    exists=False, line=f"{path} request_failed {type(error).__name__}"
                )
        content_type = response.headers.get("content-type", MISSING_CONTENT_TYPE)
        return PathReport(
            exists=response.status_code != NOT_FOUND_STATUS,
            line=f"{path} {response.status_code} {content_type} {len(response.content)}",
        )

    async def _attach_auth(
        self,
        context: MigrationRunContext,
        auth: AuthMode,
        auth_header_name: str,
        request_headers: dict[str, str],
        request_query: dict[str, str],
    ) -> None:
        if auth == "none":
            return
        service_key_secret = await self._secrets.resolve(
            ResolveSecretRequest(ref=context.service_key_ref)
        )
        service_key = service_key_secret.value.get_secret_value()
        if auth == "bearer":
            request_headers["Authorization"] = f"Bearer {service_key}"
        elif auth == "header":
            request_headers[auth_header_name] = service_key
        else:
            request_query[auth_header_name] = service_key

    async def _send(
        self,
        method: HttpMethod,
        url: str,
        request_query: dict[str, str],
        request_headers: dict[str, str],
        json_body: dict | list | None,
        text_body: str | None,
    ) -> str:
        async with (
            self._concurrency,
            httpx.AsyncClient(timeout=self._timeout_s, follow_redirects=False) as client,
        ):
            started_at = time.monotonic()
            response = await client.request(
                method,
                url,
                params=request_query,
                headers=request_headers,
                json=json_body,
                content=text_body,
            )
            latency_ms = round((time.monotonic() - started_at) * MILLISECONDS_PER_SECOND)
        return _format_response(response, latency_ms)


def _scoped_url(base_url: str, path: str) -> str:
    base_prefix = f"{base_url.rstrip('/')}/"
    url = urljoin(base_prefix, path.lstrip("/"))
    requested, base = urlsplit(url), urlsplit(base_prefix)
    stays_on_base_url = (
        requested.scheme == base.scheme
        and requested.netloc == base.netloc
        and requested.path.startswith(base.path)
    )
    if not stays_on_base_url:
        raise HostOutsideScopeError(url)
    return url


async def _ensure_public_host(url: str) -> None:
    hostname = (urlsplit(url).hostname or "").rstrip(".")
    address_infos = await asyncio.get_running_loop().getaddrinfo(hostname, None)
    resolved_addresses = {ipaddress.ip_address(info[4][0]) for info in address_infos}
    every_address_is_public = all(address.is_global for address in resolved_addresses)
    if not resolved_addresses or not every_address_is_public:
        raise NonPublicHostError(hostname)


def _format_response(response: httpx.Response, latency_ms: int) -> str:
    header_lines = "\n".join(f"  {name}: {value}" for name, value in response.headers.items())
    return (
        f"status: {response.status_code} {response.reason_phrase}\n"
        f"latency_ms: {latency_ms}\n"
        f"headers:\n{header_lines}\n"
        f"body:\n{_truncated(response.text)}"
    )


def _truncated(body: str) -> str:
    if len(body) <= MAX_BODY_CHARS:
        return body
    omitted_chars = len(body) - MAX_BODY_CHARS
    return f"{body[:MAX_BODY_CHARS]}…[truncated {omitted_chars} chars]"
