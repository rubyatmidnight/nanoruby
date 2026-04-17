import requests
import json
import time
from pathlib import Path
from .utils import safe_filename

class NanogptTTSStatus:
    """Check status of TTS generation and poll until completion."""
    
    def __init__(self):
        self.base_url = "https://nano-gpt.com/api"
        
    @classmethod
    def INPUT_TYPES(cls):
        model_list = [
            "Elevenlabs-Turbo-V2.5",
            "Kokoro-82m",
            "tts-1",
            "tts-1-hd",
            "gpt-4o-mini-tts",
        ]
        return {
            "required": {
                "run_id": ("STRING", {
                    "default": "",
                    "help": "Run ID from the TTS generator response."
                }),
                "model": (model_list, {
                    "default": "Elevenlabs-Turbo-V2.5",
                    "help": "Model used for generation."
                }),
                "api_key": ("STRING", {
                    "help": "API key for NanoGPT TTS generation."
                }),
            },
            "optional": {
                "initial_status": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "help": "Optional JSON from the generator response to shortcut if already completed."
                }),
                "custom_model": ("STRING", {
                    "default": "",
                    "help": "Override model id if not in list."
                }),
                "save_to_file": ("BOOLEAN", {
                    "default": False,
                    "help": "Append audio URL to a file when completed."
                }),
                "output_file": ("STRING", {
                    "default": "memory/tts_urls.txt",
                    "help": "Path (relative or absolute) to append the URL."
                }),
                "append_newline": ("BOOLEAN", {
                    "default": True,
                    "help": "Add newline after the URL when saving."
                }),
                "cost": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "help": "(ADVANCED) Cost override—rarely needed."
                }),
                "payment_source": ("STRING", {
                    "default": "USD",
                    "help": "(ADVANCED) Payment currency."
                }),
                "is_api_request": ("BOOLEAN", {
                    "default": True,
                    "help": "(ADVANCED) Set false to mimic frontend."
                }),
                "poll_interval": ("INT", {
                    "default": 3,
                    "min": 1,
                    "max": 60,
                    "help": "Seconds to wait between poll attempts."
                }),
                "max_polls": ("INT", {
                    "default": 60,
                    "min": 1,
                    "max": 1000,
                    "help": "Maximum poll retries before node times out."
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("status", "audio_url", "metadata")
    FUNCTION = "check_status"
    CATEGORY = "NanoGPT/tts"
    
    def check_status(self, run_id, model, api_key, initial_status="", custom_model="", save_to_file=False,
                     output_file="memory/tts_urls.txt", append_newline=True, cost=0.0, payment_source="USD",
                     is_api_request=True, poll_interval=3, max_polls=60):
        status_blob = None
        if initial_status:
            try:
                status_blob = json.loads(initial_status) if isinstance(initial_status, str) else initial_status
            except Exception:
                status_blob = None

        def _extract_audio(res):
            return res.get("audioUrl") or res.get("audio_url") or res.get("audioFile") or res.get("url") or ""

        def _save_url(url: str, path_str: str, add_nl: bool):
            try:
                path = Path(path_str)
                if not path.is_absolute():
                    path = Path(__file__).parent.parent / path
                safe_name = safe_filename(path.name)
                path = path.with_name(safe_name)
                path.parent.mkdir(parents=True, exist_ok=True)
                text = url if not add_nl else (url + ("\n" if not url.endswith("\n") else ""))
                with open(path, "a", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                print(f"Warning: failed to save URL to file: {e}")

        # If initial status already completed with audio, return immediately.
        if status_blob:
            status_val = str(status_blob.get("status", "")).lower()
            audio = _extract_audio(status_blob)
            if status_val == "completed" and audio:
                return (status_val, audio, json.dumps(status_blob))
            if not run_id:
                run_id = status_blob.get("runId") or status_blob.get("run_id") or ""

        if not run_id or run_id.strip().lower() in ["pending", "completed", "error"]:
            raise ValueError("run_id is required from the generator response; do not pass status text like 'completed'.")
        if not api_key:
            raise ValueError("API key is required.")
        effective_model = custom_model.strip() or model
        params = {"runId": run_id, "model": effective_model}
        if cost is not None:
            params["cost"] = str(cost)
        if payment_source:
            params["paymentSource"] = payment_source
        if isinstance(is_api_request, bool):
            params["isApiRequest"] = "true" if is_api_request else "false"
        headers = {"x-api-key": api_key}
        server_errors = 0
        for attempt in range(max_polls):
            try:
                response = requests.get(
                    f"{self.base_url}/tts/status",
                    params=params,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                try:
                    result = response.json()
                except Exception:
                    raise RuntimeError(f"Non-JSON status response: {response.text[:2000]}")
                status = str(result.get("status", "")).lower()
                audio_url = _extract_audio(result)
                error = result.get("error", "")
                if status == "completed" and audio_url:
                    if save_to_file:
                        _save_url(audio_url, output_file, append_newline)
                    metadata = json.dumps(result)
                    return (status, audio_url, metadata)
                elif status == "error":
                    if error == "CONTENT_POLICY_VIOLATION":
                        raise RuntimeError("TTS failed: Content Policy Violation. Please do not retry this content.")
                    raise RuntimeError(f"TTS generation failed: {error or 'Unknown error'}")
                elif status in ["pending", "in_progress", "in_queue"]:
                    print(f"Polling... attempt {attempt + 1}/{max_polls}, status: {status}")
                    if attempt < max_polls - 1:
                        time.sleep(poll_interval)
                        continue
                else:
                    print(f"Unknown status: {status}, continuing to poll...")
                    if attempt < max_polls - 1:
                        time.sleep(poll_interval)
                        continue
            except requests.exceptions.RequestException as e:
                status_code = getattr(getattr(e, "response", None), "status_code", None)
                if status_code and 500 <= status_code < 600:
                    server_errors += 1
                    if server_errors > 3:
                        error_msg = f"TTS status failed with repeated server errors (last {status_code})."
                        if hasattr(e, 'response') and e.response is not None:
                            error_msg += f"\nBody: {e.response.text[:500]}"
                        raise RuntimeError(error_msg)
                if attempt < max_polls - 1:
                    print(f"Request error (attempt {attempt + 1}): {str(e)}, retrying...")
                    time.sleep(poll_interval)
                    continue
                else:
                    error_msg = f"Status check failed: {str(e)}"
                    if hasattr(e, 'response') and e.response is not None:
                        error_msg += f"\nStatus: {e.response.status_code}\n{e.response.text}"
                    raise RuntimeError(error_msg)
        raise RuntimeError(f"TTS generation timed out after {max_polls * poll_interval} seconds")

NODE_CLASS_MAPPINGS = {
    "NanogptTTSStatus": NanogptTTSStatus,
}

