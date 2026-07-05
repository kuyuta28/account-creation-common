"""
browser_gateway_client.py — Client gọi Browser Gateway từ container.

Container (registrar/aa-proxy/mail-service) dùng module này thay vì mở browser trực tiếp.
Gateway chạy native trên host (127.0.0.1:9999), container reach qua host.docker.internal.

Flow:
  1. POST /v1/tasks {task, engine, args} → {task_id}
  2. WS   /v1/tasks/{task_id}/logs → stream log, gọi on_log mỗi line
  3. Khi nhận __END__ → GET /v1/tasks/{task_id} lấy result
  4. Raise nếu status=failed, return result nếu done.

Local 1-user, loopback, không auth.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import httpx
import websockets

_log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 600.0  # browser task có thể lâu (login, registration)


class BrowserGatewayError(Exception):
    """Gateway không reachable hoặc task failed."""


async def run_browser_task(
    gateway_url: str,
    task: str,
    *,
    engine: str | None = None,
    headless: bool | None = None,
    args: dict[str, Any] | None = None,
    on_log: Callable[[str], None] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Chạy 1 browser task trên gateway, stream log, trả result.

    Args:
        gateway_url: base URL gateway (vd http://host.docker.internal:9999).
        task: tên task đã đăng ký (vd "login_gmail").
        engine/headless: override default của task.
        args: argument cho handler (vd {"email": "..."}).
        on_log: callback mỗi log line.
        timeout: timeout chờ task hoàn tất (giây).

    Returns:
        result dict từ handler.

    Raises:
        BrowserGatewayError: gateway unreachable hoặc task failed.
    """
    base = gateway_url.rstrip("/")
    payload: dict[str, Any] = {"task": task, "args": args or {}}
    if engine is not None:
        payload["engine"] = engine
    if headless is not None:
        payload["headless"] = headless

    # 1. Tạo task
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{base}/v1/tasks", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.RequestError as exc:
        raise BrowserGatewayError(
            f"Không kết nối được Browser Gateway tại {base}: {exc}. "
            "Kiểm tra gateway đang chạy trên host (py registrar/tools/host_browser_agent.py)."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise BrowserGatewayError(
            f"Gateway trả lỗi khi tạo task: {exc.response.status_code} {exc.response.text}"
        ) from exc

    task_id = data.get("task_id")
    if not task_id:
        raise BrowserGatewayError(f"Gateway không trả task_id: {data}")

    # 2. Stream log qua WS + chờ kết thúc
    ws_url = f"{base.replace('http', 'ws')}/v1/tasks/{task_id}/logs"
    final_status: str | None = None
    try:
        async with websockets.connect(ws_url, max_size=None) as ws:
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError as exc:
                    raise BrowserGatewayError(
                        f"Task {task} timeout sau {timeout}s"
                    ) from exc
                if not isinstance(msg, str):
                    continue
                if msg.startswith("__END__ "):
                    final_status = msg.split(" ", 1)[1]
                    break
                if on_log:
                    try:
                        on_log(msg)
                    except Exception:
                        _log.exception("on_log callback lỗi, bỏ qua")
    except Exception as exc:
        # WS断了 — fallback poll status
        _log.warning("WS log stream lỗi (%s), poll status thay thế", exc)
        final_status = await _poll_status(base, task_id, timeout)

    # 3. Lấy result
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{base}/v1/tasks/{task_id}")
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPError as exc:
        raise BrowserGatewayError(f"Không lấy được kết quả task {task_id}: {exc}") from exc

    if result.get("status") == "failed" or final_status == "failed":
        raise BrowserGatewayError(
            f"Task {task} failed: {result.get('error')}"
        )
    return result.get("result") or {}


async def _poll_status(base: str, task_id: str, timeout: float) -> str | None:
    """Fallback: poll GET /v1/tasks/{id} khi WS fail."""
    import time as _time
    deadline = _time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=30.0) as client:
        while _time.monotonic() < deadline:
            try:
                resp = await client.get(f"{base}/v1/tasks/{task_id}")
                if resp.status_code == 200:
                    st = resp.json().get("status")
                    if st in ("done", "failed"):
                        return st
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1.0)
    return None
