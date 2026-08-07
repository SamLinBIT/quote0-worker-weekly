"""Dot 设备推送客户端：Canvas API + Image API.

基于参考项目 quote0-deepseek-balance/deepseek_balance/dot_push.py，
扩展支持 Image API（POST /image，整卡 PNG 直推）。
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.request
import urllib.error
from typing import Any


class DotPushError(Exception):
    pass


class DotAuthError(DotPushError):
    pass


class DotDeviceNotFoundError(DotPushError):
    pass


class DotValidationError(DotPushError):
    pass


_CANVAS_URL = "https://dot.mindreset.tech/api/authV2/open/device/{device_id}/canvas"
_IMAGE_URL = "https://dot.mindreset.tech/api/authV2/open/device/{device_id}/image"


def push_canvas(api_key: str, device_id: str, payload: dict[str, Any]) -> str:
    """推送 Canvas payload（windowData DSL 树）到 Quote/0 设备。

    Args:
        api_key: Dot API bearer token.
        device_id: Device serial number.
        payload: Complete Canvas API request body (including windowData).

    Returns:
        The server response message string.

    Raises:
        DotAuthError: Invalid API key (401/403).
        DotDeviceNotFoundError: Device not found (404).
        DotValidationError: Invalid payload (400).
        DotPushError: Other push failures.
    """
    return _post(_CANVAS_URL.format(device_id=device_id), api_key, payload, "Canvas API")


def push_image(api_key: str, device_id: str, payload: dict[str, Any]) -> str:
    """推送整卡 PNG（Image API）到 Quote/0 设备。

    Args:
        api_key: Dot API bearer token.
        device_id: Device serial number.
        payload: Image API request body: refreshNow/image/link/border/ditherType/taskAlias.

    Returns:
        The server response message string.

    Raises:
        DotAuthError: Invalid API key (401/403).
        DotDeviceNotFoundError: Device not found (404).
        DotValidationError: Invalid payload (400).
        DotPushError: Other push failures.
    """
    return _post(_IMAGE_URL.format(device_id=device_id), api_key, payload, "Image API")


def _post(url: str, api_key: str, payload: dict[str, Any], endpoint: str,
          retries: int = 3, timeout: float = 15.0) -> str:
    """POST 到 Dot API；5xx / 网络错误按 1s/2s/4s 退避重试。

    400/401/403/404 是确定的客户端错误，重试不会改变结果，直接抛。
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    ctx = ssl.create_default_context()

    last_error: DotPushError | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                status = resp.status
                resp_body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                resp_body = e.read().decode("utf-8") if e.fp else ""
            except OSError:
                resp_body = ""
        except urllib.error.URLError as e:
            last_error = DotPushError(f"Network error pushing to Dot {endpoint}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise last_error from e

        if status in (200, 201):
            try:
                data = json.loads(resp_body)
                return data.get("message", "OK")
            except json.JSONDecodeError:
                return resp_body

        if status == 400:
            msg = _extract_message(resp_body)
            raise DotValidationError(f"Dot {endpoint} validation error: {msg}")
        if status in (401, 403):
            raise DotAuthError(
                f"Dot API authentication failed (HTTP {status}). "
                "Check your DOT_API_KEY."
            )
        if status == 404:
            raise DotDeviceNotFoundError(
                f"Device {device_id_hint(url)} not found (HTTP 404). "
                "Check DOT_DEVICE_ID and ensure the content type is "
                "added to the device loop in Content Studio."
            )
        if 500 <= status < 600:
            msg = _extract_message(resp_body)
            last_error = DotPushError(f"Dot API server error (HTTP {status}): {msg}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise last_error

        raise DotPushError(f"Dot API unexpected response (HTTP {status}): {resp_body[:200]}")

    raise DotPushError(f"Dot {endpoint} push failed after {retries} attempts")  # 不可达，防御


def device_id_hint(url: str) -> str:
    """从 URL 里提取 device id 用于错误提示（尽力而为）。"""
    return url.rsplit("/", 2)[-2]


def _extract_message(resp_body: str) -> str:
    """Extract error message from JSON response body."""
    try:
        data = json.loads(resp_body)
        return data.get("message", resp_body[:200])
    except json.JSONDecodeError:
        return resp_body[:200]
