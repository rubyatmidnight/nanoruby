import requests
import json
import time
from .utils import get_api_key, get_video_models, nanogpt_video_status


def extract_video_url(data):
    output = data.get("output", {}) if isinstance(data.get("output"), dict) else {}
    video = output.get("video", {}) if isinstance(output.get("video"), dict) else {}
    return video.get("url", "") or data.get("videoUrl", "") or ""


class NanogptVideoStatus:
    """Check NanoGPT image-to-video status."""

    @classmethod
    def INPUT_TYPES(cls):
        model_choices = get_video_models()
        return {
            "required": {
                "run_id": ("STRING", {
                    "default": "",
                    "help": "The runId string from the video generator response."
                }),
                "model": (model_choices, {
                    "default": "",
                    "help": "The model name used for generating the video. Connect from generator output."
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "help": "API key for NanoGPT video generation."
                }),
            },
            "optional": {
                "custom_model": ("STRING", {
                    "default": "",
                    "help": "Override model slug"
                }),
                "initial_status": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "help": "Optional JSON from generator response."
                }),
                "poll_interval": ("INT", {
                    "default": 5,
                    "min": 1,
                    "max": 60,
                    "help": "Seconds between status checks."
                }),
                "max_polls": ("INT", {
                    "default": 120,
                    "min": 1,
                    "max": 1000,
                    "help": "Maximum times to check (timeout)."
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("run_id", "model", "status", "video_url", "metadata")
    FUNCTION = "check_status"
    CATEGORY = "NanoGPT/Video"
    
    def check_status(self, run_id, model, api_key, custom_model="", initial_status="", poll_interval=5, max_polls=120):
        """Poll until the video completes or fails."""
        status_blob = None
        if initial_status:
            try:
                status_blob = json.loads(initial_status) if isinstance(initial_status, str) else initial_status
            except Exception:
                status_blob = None

        if status_blob and isinstance(status_blob, dict):
            data = status_blob.get("data", status_blob)
            if isinstance(data, dict):
                status_val = str(data.get("status", "")).upper()
                effective_model = custom_model.strip() or model or data.get("model", "")
                effective_run_id = run_id or data.get("runId") or data.get("run_id") or ""
                video_url = extract_video_url(data)
                if status_val == "COMPLETED" and video_url:
                    return (effective_run_id, effective_model, status_val, video_url, json.dumps(data))
                if not run_id:
                    run_id = effective_run_id

        if not run_id:
            raise ValueError("run_id is required")

        api_key = get_api_key("video", api_key)
        if not api_key:
            raise ValueError("API key is required.")

        effective_model = custom_model.strip() or model
        last_metadata = None
        for attempt in range(max_polls):
            try:
                result = nanogpt_video_status(run_id, effective_model, api_key, timeout_s=30)
                data = result.get("data", result)
                status = data.get("status", "").upper()
                video_url = ""
                last_metadata = json.dumps({
                    "runId": run_id,
                    "status": status,
                    "model": effective_model,
                    "request_id": data.get("request_id"),
                    "details": data.get("details"),
                    "error": data.get("error"),
                    "api_response": data
                })
                if status == "COMPLETED":
                    video_url = extract_video_url(data)
                    if video_url:
                        print(f"Video generation completed after {attempt+1} poll(s): {video_url}")
                        return (run_id, effective_model, status, video_url, last_metadata)
                elif status == "FAILED":
                    error = data.get("error", "Unknown error")
                    user_friendly = data.get("userFriendlyError", error)
                    print(f"Video generation failed after {attempt+1} poll(s): {user_friendly}")
                    raise RuntimeError(f"Video generation failed: {user_friendly}")
                elif status in ["IN_QUEUE", "IN_PROGRESS", "PENDING"]:
                    if attempt % 5 == 0 or attempt == max_polls - 1:
                        print(f"Polling... attempt {attempt + 1}/{max_polls}, status: {status}")
                    if attempt < max_polls - 1:
                        time.sleep(poll_interval)
                        continue
                else:
                    print(f"Unknown status: {status} (poll {attempt+1})")
                    if attempt < max_polls - 1:
                        time.sleep(poll_interval)
                        continue
            except requests.exceptions.RequestException as e:
                if attempt < max_polls - 1:
                    print(f"Request error (attempt {attempt + 1}): {str(e)}, retrying...")
                    time.sleep(poll_interval)
                    continue
                else:
                    error_msg = f"Status check failed: {str(e)}"
                    if hasattr(e, 'response') and e.response is not None:
                        error_msg += f"\nStatus: {e.response.status_code}\n{e.response.text}"
                    print(error_msg)
                    raise RuntimeError(error_msg)
        print("Video generation timed out.")
        raise RuntimeError(f"Video generation timed out after {max_polls * poll_interval} seconds. Metadata: {last_metadata}")

NODE_CLASS_MAPPINGS = {
    "NanogptVideoStatus": NanogptVideoStatus,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanogptVideoStatus": "NanoGPT Video Status",
}

