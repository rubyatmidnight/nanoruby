import requests
import os
import socket
import tempfile
import ipaddress
from pathlib import Path
from urllib.parse import urlparse
from .utils import safe_filename, folder_paths


MAX_VIDEO_BYTES = 2 * 1024 * 1024 * 1024


def _validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Video URL must use HTTPS.")
    for info in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ValueError("Video URL resolves to a private address.")

class NanogptVideoDownloader:
    """Download video from URL and save locally."""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_url": ("STRING", {
                    "default": "",
                    "help": "URL of video to download (output from status node)."
                }),
            },
            "optional": {
                "filename": ("STRING", {
                    "default": "",
                    "help": "Optional output filename (leave blank for auto)"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "download_video"
    CATEGORY = "NanoGPT/Video"
    
    def download_video(self, video_url, filename=""):
        if not video_url:
            raise ValueError("video_url is required")
        _validate_url(video_url)
        output_dir = folder_paths() / "videos"
        output_dir.mkdir(parents=True, exist_ok=True)
        url_base = video_url.split('?')[0]
        ext = Path(url_base).suffix or ".mp4"
        stem = Path(url_base).stem
        if not filename:
            filename = f"nanogpt_video_{stem}{ext}"
        filename = safe_filename(filename)
        if not filename.lower().endswith(('.mp4', '.mov', '.webm')):
            filename += ".mp4"
        filepath = output_dir / filename
        temp_path = None
        try:
            response = requests.get(video_url, timeout=(15, 120), stream=True)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
            if content_type and not content_type.startswith("video/") and content_type != "application/octet-stream":
                raise RuntimeError(f"Unexpected video content type: {content_type}")
            length = int(response.headers.get("Content-Length", "0") or 0)
            if length > MAX_VIDEO_BYTES:
                raise RuntimeError("Video exceeds the 2 GiB download limit.")
            handle, temp_name = tempfile.mkstemp(dir=output_dir, suffix=".part")
            temp_path = Path(temp_name)
            total = 0
            with os.fdopen(handle, "wb") as stream:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        total += len(chunk)
                        if total > MAX_VIDEO_BYTES:
                            raise RuntimeError("Video exceeds the 2 GiB download limit.")
                        stream.write(chunk)
            os.replace(temp_path, filepath)
            return (str(filepath),)
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Download failed: {exc}") from exc
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()

NODE_CLASS_MAPPINGS = {
    "NanogptVideoDownloader": NanogptVideoDownloader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanogptVideoDownloader": "NanoGPT Video Downloader",
}

