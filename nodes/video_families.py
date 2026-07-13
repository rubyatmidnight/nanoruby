"""
Per-family NanoGPT video nodes.
One node per model class with only the options that family supports.
"""
import json
from .utils import encode_image, get_api_key, nanogpt_video_generate


SEEDANCE_VARIANTS = {
    "1.5 Pro Fast": "bytedance-seedance-v1.5-pro-fast",
    "2.0 Turbo": "bytedance-seedance-2-0",
    "2.0 Fast Turbo": "bytedance-seedance-2-0-fast",
}

SEEDANCE_ASPECTS = ["16:9", "9:16", "4:3", "3:4", "1:1", "21:9"]
SEEDANCE_DURATIONS = [str(s) for s in range(4, 13)]
SEEDANCE_RESOLUTIONS = ["720p", "1080p"]


def _run_video(payload, api_key, *, family, session_id=""):
    """Shared call + metadata builder."""
    result = nanogpt_video_generate(payload, api_key, timeout_s=120)
    run_id = result.get("runId") or result.get("requestId")
    status = result.get("status", "pending")
    if "cost" in result:
        print(f"API: {family} cost was {result['cost']}, balance now {result.get('remainingBalance')}")
    safe_request = dict(payload)
    if "imageDataUrl" in safe_request:
        safe_request["imageDataUrl"] = f"<redacted:{len(safe_request['imageDataUrl'])} chars>"
    from .video_queue import append_video_job
    queue_path = append_video_job(run_id, payload.get("model", ""), session_id)
    metadata = json.dumps({
        "family": family,
        "runId": run_id,
        "status": status,
        "request": safe_request,
        "queue_path": str(queue_path),
        "api_response": result,
    })
    return run_id, payload.get("model", ""), status, metadata


def _maybe_attach_image(payload, image):
    if image is None:
        return
    encoded = encode_image(image)
    payload["imageDataUrl"] = f"data:image/png;base64,{encoded}"


class NanogptSeedance:
    """NanoGPT Seedance video (T2V/I2V)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "A cat riding atop a majestic seahorse in the himalayas",
                }),
                "variant": (list(SEEDANCE_VARIANTS.keys()), {"default": "1.5 Pro Fast"}),
                "resolution": (SEEDANCE_RESOLUTIONS, {"default": "720p"}),
                "duration": (SEEDANCE_DURATIONS, {"default": "5"}),
                "aspect_ratio": (SEEDANCE_ASPECTS, {"default": "16:9"}),
                "generate_audio": ("BOOLEAN", {"default": True}),
                "camera_fixed": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "image": ("IMAGE",),
                "api_key": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 0xffffffffffffffff}),
                "session_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("run_id", "model", "status", "metadata")
    FUNCTION = "generate"
    CATEGORY = "NanoGPT/Video"

    def generate(self, prompt, variant, resolution, duration, aspect_ratio,
                 generate_audio, camera_fixed, image=None, api_key="", seed=-1, session_id=""):
        key = get_api_key("video", api_key)
        if not key:
            raise ValueError("API key is required.")
        payload = {
            "model": SEEDANCE_VARIANTS[variant],
            "prompt": prompt.strip(),
            "resolution": resolution,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "generateAudio": bool(generate_audio),
            "camera_fixed": bool(camera_fixed),
        }
        if isinstance(seed, int) and seed >= 0:
            payload["seed"] = seed
        _maybe_attach_image(payload, image)
        return _run_video(payload, key, family="seedance", session_id=session_id)


class NanogptWan22:
    """NanoGPT Wan 2.2 14b video (T2V/I2V)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "A cat riding atop a majestic seahorse in the himalayas",
                }),
                "resolution": (["480p", "720p"], {"default": "720p"}),
                "duration": (["5", "8"], {"default": "5"}),
                "orientation": (["landscape", "portrait"], {
                    "default": "landscape",
                    "tooltip": "T2V only; ignored for I2V.",
                }),
            },
            "optional": {
                "image": ("IMAGE",),
                "api_key": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 0xffffffffffffffff}),
                "session_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("run_id", "model", "status", "metadata")
    FUNCTION = "generate"
    CATEGORY = "NanoGPT/Video"

    def generate(self, prompt, resolution, duration, orientation,
                 image=None, api_key="", seed=-1, session_id=""):
        key = get_api_key("video", api_key)
        if not key:
            raise ValueError("API key is required.")
        payload = {
            "model": "wan-video-22",
            "prompt": prompt.strip(),
            "resolution": resolution,
            "duration": duration,
        }
        if image is None:
            payload["orientation"] = orientation
        if isinstance(seed, int) and seed >= 0:
            payload["seed"] = seed
        _maybe_attach_image(payload, image)
        return _run_video(payload, key, family="wan-2.2-14b", session_id=session_id)


NODE_CLASS_MAPPINGS = {
    "NanogptSeedance": NanogptSeedance,
    "NanogptWan22": NanogptWan22,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanogptSeedance": "NanoGPT Seedance",
    "NanogptWan22": "NanoGPT Wan 2.2 14b",
}
