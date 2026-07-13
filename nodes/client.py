"""Shared NanoGPT API client."""

import json
from typing import Any, Dict, List, Optional

import requests


BASE_URL = "https://nano-gpt.com"


class NanoGPTError(RuntimeError):
    """Normalized NanoGPT API error."""


def _error_message(response: requests.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if body.get("message"):
                return str(body["message"])
    except ValueError:
        pass
    text = (response.text or "").strip()
    return text[:500] or response.reason or "Unknown API error"


class NanoGPTClient:
    def __init__(self, api_key: str, timeout: int = 120, session=None):
        if not api_key:
            raise ValueError("NanoGPT API key is required.")
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()

    def _headers(self, video: bool = False) -> dict:
        if video:
            return {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip, deflate",
            }
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }

    def request(self, method: str, path: str, *, video=False, **kwargs) -> Dict[str, Any]:
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("headers", self._headers(video))
        try:
            response = self.session.request(method, f"{BASE_URL}{path}", **kwargs)
            response.raise_for_status()
            result = response.json()
        except requests.HTTPError as exc:
            response = exc.response
            message = _error_message(response) if response is not None else str(exc)
            status = response.status_code if response is not None else "unknown"
            raise NanoGPTError(f"NanoGPT API error {status}: {message}") from exc
        except requests.RequestException as exc:
            raise NanoGPTError(f"NanoGPT request failed: {exc}") from exc
        except ValueError as exc:
            raise NanoGPTError("NanoGPT returned invalid JSON.") from exc
        if not isinstance(result, dict):
            raise NanoGPTError("NanoGPT returned non-object JSON.")
        return result

    def list_text_models(self, detailed: bool = True) -> Dict[str, Any]:
        suffix = "?detailed=true" if detailed else ""
        return self.request("GET", f"/api/v1/models{suffix}")

    def list_video_models(self) -> Dict[str, Any]:
        return self.request("GET", "/api/v1/video-models")

    def chat(self, payload: dict) -> Dict[str, Any]:
        return self.request("POST", "/api/v1/chat/completions", json=payload)

    def generate_video(self, payload: dict) -> Dict[str, Any]:
        return self.request("POST", "/api/generate-video", video=True, json=payload)

    def video_status(self, request_id: str) -> Dict[str, Any]:
        return self.request(
            "GET",
            "/api/video/status",
            video=True,
            params={"requestId": request_id},
            timeout=30,
        )


def extract_chat_result(result: dict) -> tuple:
    reply = result.get("reply")
    reasoning = ""
    if not reply:
        choices = result.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0] if isinstance(choices[0], dict) else {}
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            reply = message.get("content") or choice.get("text")
            reasoning = message.get("reasoning") or message.get("reasoning_content") or ""
    if not isinstance(reply, str):
        raise NanoGPTError("Chat response did not contain text.")
    return reply, reasoning, result.get("usage") or {}


def normalize_messages(messages: Any) -> List[dict]:
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except json.JSONDecodeError as exc:
            raise ValueError("Messages must be valid JSON.") from exc
    if not isinstance(messages, list):
        raise ValueError("Messages must be a JSON array.")
    normalized = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Each message must be an object.")
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or content is None:
            raise ValueError("Each message needs role and content.")
        normalized.append(dict(message))
    return normalized


def build_chat_payload(
    model: str,
    messages: Any,
    *,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    reasoning_effort: str = "auto",
) -> dict:
    normalized = normalize_messages(messages)
    if system_prompt.strip():
        normalized = [m for m in normalized if m.get("role") != "system"]
        normalized.insert(0, {"role": "system", "content": system_prompt.strip()})
    payload = {"model": model, "messages": normalized}
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if reasoning_effort != "auto":
        payload["reasoning_effort"] = reasoning_effort
    return payload
