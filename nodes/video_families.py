"""
Per-family NanoGPT video nodes.
One node per model class with only the options that family supports.
"""
import json
import requests

from .utils import encode_image, get_api_key, nanogpt_video_generate


SEEDANCE_VARIANTS = {
    "1.5 Pro Fast": "bytedance-seedance-v1.5-pro-fast",
    "2.0 Turbo": "bytedance-seedance-2-0",
    "2.0 Fast Turbo": "bytedance-seedance-2-0-fast",
}

SEEDANCE_ASPECTS = ["16:9", "9:16", "4:3", "3:4", "1:1", "21:9"]
SEEDANCE_DURATIONS = [str(s) for s in range(4, 13)]
SEEDANCE_RESOLUTIONS = ["720p", "1080p"]


def _run_video(payload, api_key, *, family):
    """Shared call + metadata builder."""
    try:
        result = nanogpt_video_generate(payload, api_key, timeout_s=120)
    except requests.exceptions.RequestException as exc:
        msg = f"API request failed: {exc}"
        if getattr(exc, "response", None) is not None:
            msg += f"\nStatus: {exc.response.status_code}\n{exc.response.text}"
        raise RuntimeError(msg)
    run_id = result.get("runId", "")
    status = result.get("status", "pending")
    if "cost" in result:
        print(f"API: {family} cost was {result['cost']}, balance now {result.get('remainingBalance')}")
    metadata = json.dumps({
        "family": family,
        "runId": run_id,
        "status": status,
        "request": payload,
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
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("run_id", "model", "status", "metadata")
    FUNCTION = "generate"
    CATEGORY = "NanoGPT/Video"

    def generate(self, prompt, variant, resolution, duration, aspect_ratio,
                 generate_audio, camera_fixed, image=None, api_key="", seed=-1):
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
        return _run_video(payload, key, family="seedance")


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
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("run_id", "model", "status", "metadata")
    FUNCTION = "generate"
    CATEGORY = "NanoGPT/Video"

    def generate(self, prompt, resolution, duration, orientation,
                 image=None, api_key="", seed=-1):
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
        return _run_video(payload, key, family="wan-2.2-14b")


NODE_CLASS_MAPPINGS = {
    "NanogptSeedance": NanogptSeedance,
    "NanogptWan22": NanogptWan22,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanogptSeedance": "NanoGPT Seedance",
    "NanogptWan22": "NanoGPT Wan 2.2 14b",
}
