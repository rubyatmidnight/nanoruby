import json
from .utils import get_api_key, nanogpt_video_status


TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELED"}
PENDING_STATUSES = {"IN_QUEUE", "IN_PROGRESS", "PENDING"}


def extract_video_url(data):
    output = data.get("output", {}) if isinstance(data.get("output"), dict) else {}
    video = output.get("video", {}) if isinstance(output.get("video"), dict) else {}
    return video.get("url", "") or data.get("videoUrl", "") or ""


def unwrap_response(blob):
    """Return (top, data) from a status response or pre-supplied JSON blob."""
    if not isinstance(blob, dict):
        return {}, {}
    data = blob.get("data") if isinstance(blob.get("data"), dict) else blob
    return blob, data


class NanogptVideoStatus:
    """Check NanoGPT video generation status via unified endpoint."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "run_id": ("STRING", {
                    "default": "",
                    "help": "Job id (vid_...) or runId from the generator response."
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "help": "API key for NanoGPT video."
                }),
            },
            "optional": {
                "initial_status": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "help": "Optional JSON from generator response — short-circuits if already COMPLETED."
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("run_id", "model", "status", "video_url", "metadata")
    FUNCTION = "check_status"
    CATEGORY = "NanoGPT/Video"

    def check_status(self, run_id, api_key, initial_status="", poll_interval=5, max_polls=120):
        """Check the unified video status once."""
        if initial_status:
            try:
                blob = json.loads(initial_status) if isinstance(initial_status, str) else initial_status
                top, data = unwrap_response(blob)
                status_val = str(data.get("status", "")).upper()
                seeded_run_id = top.get("requestId") or top.get("runId") or data.get("requestId") or data.get("runId") or ""
                seeded_model = top.get("model") or data.get("model") or ""
                if status_val == "COMPLETED":
                    video_url = extract_video_url(data)
                    if video_url:
                        return (run_id or seeded_run_id, seeded_model, status_val, video_url, json.dumps(top))
                if not run_id:
                    run_id = seeded_run_id
            except Exception:
                pass

        if not run_id:
            raise ValueError("run_id is required")

        api_key = get_api_key("video", api_key)
        if not api_key:
            raise ValueError("API key is required.")

        result = nanogpt_video_status(run_id, api_key, timeout_s=30)
        top, data = unwrap_response(result)
        status = str(data.get("status", "")).upper()
        api_model = top.get("model") or data.get("model") or ""
        metadata = json.dumps({
            "requestId": top.get("requestId") or run_id,
            "status": status,
            "model": api_model,
            "cost": data.get("cost"),
            "details": data.get("details"),
            "error": data.get("error"),
            "api_response": result,
        })
        video_url = extract_video_url(data)
        if status == "COMPLETED" and not video_url:
            raise RuntimeError("Video completed without an output URL.")
        if status == "FAILED":
            message = data.get("userFriendlyError") or data.get("error") or "Unknown error"
            raise RuntimeError(f"Video generation failed: {message}")
        if status == "CANCELED":
            raise RuntimeError("Video generation was canceled.")
        return (run_id, api_model, status or "UNKNOWN", video_url, metadata)


NODE_CLASS_MAPPINGS = {
    "NanogptVideoStatus": NanogptVideoStatus,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanogptVideoStatus": "NanoGPT Video Status",
}
