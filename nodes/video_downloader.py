import requests
from pathlib import Path
from .utils import safe_filename, folder_paths

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
    CATEGORY = "nanogpt/video"
    
    def download_video(self, video_url, filename=""):
        if not video_url:
            raise ValueError("video_url is required")
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
        if filepath.exists():
            print(f"Warning: File {filepath} will be overwritten.")
        if not video_url:
            raise RuntimeError("No video URL provided to download.")
        try:
            response = requests.get(video_url, timeout=120, stream=True)
            response.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"Video downloaded successfully: {filepath}")
            return (str(filepath),)
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Download failed: {str(e)}")

NODE_CLASS_MAPPINGS = {
    "NanogptVideoDownloader": NanogptVideoDownloader,
}

