import os
import base64
import re
import json
from pathlib import Path
import requests
try:
    import dotenv
except Exception:  # pragma: no cover
    dotenv = None

# Load .env from project root (parent of nodes/)
if dotenv is not None:
    dotenv.load_dotenv(Path(__file__).parent.parent / ".env")

def get_api_key(type="master",api_key_override=""):
    """Get API key from override or environment."""
    if api_key_override:
        return api_key_override
    if type == "master" and os.getenv("NANOGPT_MASTER_API_KEY"):
        return os.getenv("NANOGPT_MASTER_API_KEY")
    if type == "video" and os.getenv("NANOGPT_VIDEO_KEY"):
        return os.getenv("NANOGPT_VIDEO_KEY")
    if type == "tts" and os.getenv("NANOGPT_TTS_KEY"):
        return os.getenv("NANOGPT_TTS_KEY")
    if type == "image" and os.getenv("NANOGPT_IMAGE_KEY"):
        return os.getenv("NANOGPT_IMAGE_KEY")
    if type == "audio" and os.getenv("NANOGPT_AUDIO_KEY"):
        return os.getenv("NANOGPT_AUDIO_KEY")
    return os.getenv(f"NANOGPT_{type.upper()}_API_KEY")


def safe_filename(filename):
    # Only allow safe chars in filename for Windows compatibility.
    return re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

def _load_model_file(path):
    """Load model ids from json file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [m.get("id") for m in json.load(f).get("data", []) if m.get("id")]
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return []

def load_models(contains_any=None, favorites_first=True, fallback=None):
    """Load models with optional substring filter."""
    contains_any = [c.lower() for c in contains_any or []]
    fallback = fallback or []
    nodes_models = _load_model_file(Path(__file__).parent / "models.json")
    root_models = _load_model_file(Path(__file__).parent.parent / "models.json")
    fav_models = _load_model_file(Path(__file__).parent / "models_favorite.json")

    def apply_filter(models):
        if not contains_any:
            return models
        return [m for m in models if any(tok in m.lower() for tok in contains_any)]

    source_models = nodes_models if nodes_models else root_models
    filtered_root = apply_filter(source_models)
    filtered_fav = apply_filter(fav_models)

    combined = []
    seen = set()
    if favorites_first and filtered_fav:
        for mid in filtered_fav:
            if mid not in seen:
                combined.append(mid)
                seen.add(mid)

    source = filtered_root if filtered_root else filtered_fav
    for mid in source:
        if mid not in seen:
            combined.append(mid)
            seen.add(mid)

    if not combined:
        combined = fallback[:]

    return combined


def update_models_list(api_key: str, detailed: bool = False, timeout_s: int = 30) -> dict:
    url = "https://nano-gpt.com/api/v1/models"
    if detailed:
        url = f"{url}?detailed=true"

    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json()

    out_path = Path(__file__).parent / ("models_detailed.json" if detailed else "models.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    count = 0
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        count = len(data["data"])

    return {"path": str(out_path), "count": count, "detailed": detailed}

VIDEO_MODEL_PROFILES = {
    "wan-video-image-to-video": {
        "label": "Wan 2.6 Image-To-Video Pro",
        "durations": ["5s", "10s", "15s"],
        "resolutions": ["1080p", "2k", "4k"],
        "notes": ["shot type", "prompt expansion"],
    },
    "wan-video-22-turbo": {
        "label": "Wan 2.2 Turbo",
        "durations": [],
        "resolutions": ["480p", "580p", "720p"],
        "notes": ["safety checker", "prompt expansion"],
    },
    "wan-video-22": {
        "label": "Wan 2.2 14B",
        "durations": ["5s", "8s"],
        "resolutions": ["480p", "720p"],
        "notes": [],
    },
    "wan-wavespeed-25": {
        "label": "Wan 2.5",
        "durations": ["5s", "8s"],
        "resolutions": ["480p", "720p", "1080p"],
        "notes": ["prompt expansion"],
    },
    "wan-wavespeed-26": {
        "label": "Wan 2.6 Flash",
        "durations": [f"{seconds}s" for seconds in range(2, 16)],
        "resolutions": ["720p", "1080p"],
        "notes": ["shot type", "audio doubles cost"],
    },
}


def get_video_models() -> list:
    return list(VIDEO_MODEL_PROFILES.keys())


def get_video_model_profile(model_slug: str) -> dict:
    return VIDEO_MODEL_PROFILES.get(model_slug, {})


def validate_video_request(model_slug: str, duration: str, resolution: str) -> None:
    profile = get_video_model_profile(model_slug)
    allowed_durations = profile.get("durations") or []
    allowed_resolutions = profile.get("resolutions") or []

    if duration and duration != "auto" and allowed_durations and duration not in allowed_durations:
        raise ValueError(f"{model_slug} supports durations: {', '.join(allowed_durations)}")

    if resolution and resolution != "auto" and allowed_resolutions and resolution not in allowed_resolutions:
        raise ValueError(f"{model_slug} supports resolutions: {', '.join(allowed_resolutions)}")


def _video_headers(api_key: str) -> dict:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


def nanogpt_video_generate(payload: dict, api_key: str, timeout_s: int = 120) -> dict:
    resp = requests.post(
        "https://nano-gpt.com/api/generate-video",
        json=payload,
        headers=_video_headers(api_key),
        timeout=timeout_s,
    )
    resp.raise_for_status()
    out = resp.json()
    if not isinstance(out, dict):
        raise RuntimeError("Video API returned non-object JSON")
    return out


def nanogpt_video_status(run_id: str, model_slug: str, api_key: str, timeout_s: int = 30) -> dict:
    resp = requests.get(
        "https://nano-gpt.com/api/generate-video/status",
        params={"runId": run_id, "modelSlug": model_slug},
        headers={"x-api-key": api_key},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    out = resp.json()
    if not isinstance(out, dict):
        raise RuntimeError("Video status returned non-object JSON")
    return out

def folder_paths():
    """Return the path to the output directory."""
    return Path(__file__).parent.parent.parent / "output"

def encode_image(image_tensor):
    """Convert ComfyUI image tensor to base64 PNG."""
    import numpy as np
    from PIL import Image
    import io
    
    if hasattr(image_tensor, 'cpu'):
        image_array = image_tensor.cpu().numpy()
    elif isinstance(image_tensor, dict):
        image_array = image_tensor
    else:
        image_array = np.asarray(image_tensor)
    
    if len(image_array.shape) == 4:
        image_array = image_array[0]
    
    image_array = image_array.astype(np.float32)
    if image_array.max() > 1.0:
        image_array = image_array / 255.0
    
    image_array = (image_array * 255).astype(np.uint8)
    
    if len(image_array.shape) == 3 and image_array.shape[2] == 4:
        img = Image.fromarray(image_array[:, :, :3], mode='RGB')
    else:
        img = Image.fromarray(image_array)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return img_base64

# Expose the .env path for reference (in project root).
ENV_FILE_PATH = Path(__file__).parent.parent / ".env"
