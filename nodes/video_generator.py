import json
import requests
from .utils import encode_image, get_api_key, get_video_model_profile, get_video_models, nanogpt_video_generate, update_models_list as _update_models_list, validate_video_request


def _clean_text(value):
    return value.strip() if isinstance(value, str) else ""


def build_image_to_video_payload(
    prompt,
    model,
    duration="5s",
    aspect_ratio="16:9",
    resolution="720p",
    camera_fixed=False,
    negative_prompt="",
    seed=-1,
    image_url="",
    image_data_url="",
):
    payload = {
        "model": model,
        "prompt": prompt.strip(),
    }
    if duration and duration != "auto":
        payload["duration"] = duration
    if aspect_ratio and aspect_ratio != "auto":
        payload["aspect_ratio"] = aspect_ratio
    if resolution and resolution != "auto":
        payload["resolution"] = resolution
    if camera_fixed:
        payload["camera_fixed"] = True
    if negative_prompt.strip():
        payload["negative_prompt"] = negative_prompt.strip()
    if isinstance(seed, int) and seed >= 0:
        payload["seed"] = seed
    if image_data_url:
        payload["imageDataUrl"] = image_data_url
    elif image_url:
        payload["imageUrl"] = image_url
    return payload


class NanogptImageToVideo:
    """Generate image-to-video with NanoGPT."""

    @classmethod
    def INPUT_TYPES(cls):
        model_choices = get_video_models()
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "Add gentle cinematic motion to this scene.",
                    "help": "Prompt describing the motion to generate."
                }),
                "model": (model_choices, {
                    "default": model_choices[0] if model_choices else "",
                    "help": "Image-to-video model slug."
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "help": "NanoGPT API key."
                }),
            },
            "optional": {
                "image": ("IMAGE", {
                    "help": "ComfyUI image input."
                }),
                "image_url": ("STRING", {
                    "default": "",
                    "help": "Public image URL."
                }),
                "image_data_url": ("STRING", {
                    "default": "",
                    "help": "Base64 data URL image."
                }),
                "duration": (["auto"] + [f"{seconds}s" for seconds in range(2, 16)], {
                    "default": "5s",
                    "help": "Requested duration."
                }),
                "aspect_ratio": (["auto", "16:9", "9:16", "1:1", "3:4", "4:3"], {
                    "default": "16:9",
                    "help": "Requested aspect ratio."
                }),
                "resolution": (["auto", "480p", "580p", "720p", "1080p", "2k", "4k"], {
                    "default": "1080p",
                    "help": "Requested resolution."
                }),
                "camera_fixed": ("BOOLEAN", {
                    "default": False,
                    "help": "Keep camera static."
                }),
                "negative_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "help": "Optional negative prompt."
                }),
                "seed": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 0xffffffffffffffff,
                    "help": "Seed override."
                }),
                "custom_model": ("STRING", {
                    "default": "",
                    "help": "Override model slug."
                }),
                "update_models_list": ("BOOLEAN", {
                    "default": False,
                    "help": "Fetch latest models into nodes/models.json."
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("run_id", "model", "status", "metadata")
    FUNCTION = "generate_video"
    CATEGORY = "NanoGPT/Video/Advanced"

    def generate_video(
        self,
        prompt,
        model,
        api_key,
        image=None,
        image_url="",
        image_data_url="",
        duration="5s",
        aspect_ratio="16:9",
        resolution="720p",
        camera_fixed=False,
        negative_prompt="",
        seed=-1,
        custom_model="",
        update_models_list=False,
    ):
        api_key = get_api_key("video", api_key)
        if not api_key:
            raise ValueError("API key is required.")

        update_info = None
        if update_models_list:
            try:
                update_info = _update_models_list(api_key=api_key, detailed=False)
            except Exception as e:
                update_info = {"error": str(e)}

        effective_model = _clean_text(custom_model) or model
        validate_video_request(effective_model, duration, resolution)
        model_profile = get_video_model_profile(effective_model)
        payload = build_image_to_video_payload(
            prompt=prompt,
            model=effective_model,
            duration=duration,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            camera_fixed=camera_fixed,
            negative_prompt=negative_prompt,
            seed=seed,
            image_url=_clean_text(image_url),
            image_data_url=_clean_text(image_data_url),
        )

        if "imageDataUrl" not in payload and "imageUrl" not in payload:
            if image is None:
                raise ValueError("Provide image, image_url, or image_data_url.")
            image_base64 = encode_image(image)
            payload["imageDataUrl"] = f"data:image/png;base64,{image_base64}"

        try:
            result = nanogpt_video_generate(payload, api_key, timeout_s=120)
            run_id = result.get("runId", "")
            status = result.get("status", "pending")
            metadata = json.dumps({
                "runId": run_id,
                "status": status,
                "model": effective_model,
                "model_profile": model_profile,
                "payload": payload,
                "models_update": update_info,
                "api_response": result,
            })
            return (run_id, effective_model, status, metadata)
        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            if hasattr(e, "response") and e.response is not None:
                error_msg += f"\nStatus: {e.response.status_code}\n{e.response.text}"
            raise RuntimeError(error_msg)


NODE_CLASS_MAPPINGS = {
    "NanogptImageToVideo": NanogptImageToVideo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanogptImageToVideo": "NanoGPT Image to Video",
}

