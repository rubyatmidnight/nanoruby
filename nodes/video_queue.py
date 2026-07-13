"""File-backed video job sessions."""

import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .utils import get_api_key, get_output_directory, nanogpt_video_status
from .video_status import extract_video_url, unwrap_response


_session_id = None
_session_date = None


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_session_id(reset=False):
    global _session_id, _session_date
    date = datetime.now().strftime("%Y%m%d")
    if reset or not _session_id or _session_date != date:
        _session_id = secrets.token_hex(1)
        _session_date = date
    return _session_id


def session_path(session_id=""):
    now = datetime.now()
    session_id = session_id.strip() or get_session_id()
    safe_id = "".join(char for char in session_id if char.isalnum() or char in "-_")[:64]
    if not safe_id:
        raise ValueError("Invalid session ID.")
    return get_output_directory() / "nanogpt" / "video_jobs" / now.strftime("%Y") / now.strftime("%m%d") / f"{safe_id}.json"


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def append_video_job(run_id, model="", session_id="", metadata=None):
    if not run_id:
        raise ValueError("run_id is required.")
    path = session_path(session_id)
    data = _load(path)
    data.setdefault("session_id", path.stem)
    data.setdefault("created_at", _now())
    data.setdefault("active", [])
    data.setdefault("archive", [])
    if not any(job.get("run_id") == run_id for job in data["active"] + data["archive"]):
        data["active"].append({
            "run_id": run_id,
            "model": model,
            "submitted_at": _now(),
            "metadata": metadata or {},
        })
    data["updated_at"] = _now()
    _write(path, data)
    return path


class NanogptVideoSession:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}, "optional": {"reset": ("BOOLEAN", {"default": False})}}

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("session_id", "queue_path")
    FUNCTION = "create"
    CATEGORY = "NanoGPT/Video"

    def create(self, reset=False):
        identifier = get_session_id(reset)
        return (identifier, str(session_path(identifier)))


class NanogptVideoBatchStatus:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"session_id": ("STRING", {"default": ""})},
            "optional": {"api_key": ("STRING", {"default": ""})},
        }

    RETURN_TYPES = ("JSON", "STRING", "INT", "INT")
    RETURN_NAMES = ("summary", "video_urls", "pending_count", "terminal_count")
    FUNCTION = "check_all"
    CATEGORY = "NanoGPT/Video"

    def check_all(self, session_id, api_key=""):
        key = get_api_key("video", api_key)
        if not key:
            raise ValueError("API key is required.")
        path = session_path(session_id)
        data = _load(path)
        active = data.get("active", [])
        remaining = []
        terminal = []
        urls = []
        results = []
        for job in active:
            run_id = job.get("run_id", "")
            result = nanogpt_video_status(run_id, key)
            top, status_data = unwrap_response(result)
            status = str(status_data.get("status", "")).upper()
            video_url = extract_video_url(status_data)
            checked = dict(job)
            checked.update({"status": status, "checked_at": _now(), "video_url": video_url})
            results.append(checked)
            if video_url:
                urls.append(video_url)
            if status in {"COMPLETED", "FAILED", "CANCELED"}:
                checked["api_response"] = result
                terminal.append(checked)
            else:
                remaining.append(checked)
        data["active"] = remaining
        data.setdefault("archive", []).extend(terminal)
        data["updated_at"] = _now()
        _write(path, data)
        summary = {
            "session_id": path.stem,
            "queue_path": str(path),
            "results": results,
            "pending_count": len(remaining),
            "terminal_count": len(terminal),
        }
        return (summary, "\n".join(urls), len(remaining), len(terminal))


NODE_CLASS_MAPPINGS = {
    "NanogptVideoSession": NanogptVideoSession,
    "NanogptVideoBatchStatus": NanogptVideoBatchStatus,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanogptVideoSession": "NanoGPT Video Session",
    "NanogptVideoBatchStatus": "NanoGPT Video Batch Status",
}
