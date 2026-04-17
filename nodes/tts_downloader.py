import requests
from pathlib import Path
from .utils import safe_filename, folder_paths

class NanogptTTSDownloader:
    """Download TTS audio from URL and save locally."""
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_url": ("STRING", {
                    "default": "",
                    "help": "TTS audio file URL (from status node)."
                }),
            },
            "optional": {
                "filename": ("STRING", {
                    "default": "",
                    "help": "Optional audio filename (blank for auto)."
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("audio_path",)
    FUNCTION = "download_audio"
    CATEGORY = "nanogpt/tts"
    
    def download_audio(self, audio_url, filename=""):
        if not audio_url:
            raise ValueError("audio_url is required")
        output_dir = folder_paths() / "audio"
        output_dir.mkdir(parents=True, exist_ok=True)
        supported_exts = ['.mp3', '.wav', '.opus', '.flac', '.m4a', '.aac']
        if not filename:
            url_path = Path(audio_url.split('?')[0])
            ext = url_path.suffix.lower()
            ext = ext if ext in supported_exts else ".mp3"
            stem = safe_filename(url_path.stem)
            filename = f"nanogpt_tts_{stem}{ext}"
        else:
            if not any(filename.lower().endswith(ext) for ext in supported_exts):
                filename += ".mp3"
        filepath = output_dir / safe_filename(filename)
        try:
            response = requests.get(audio_url, timeout=120, stream=True)
            response.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"Audio downloaded successfully: {filepath}")
            return (str(filepath),)
        except requests.exceptions.RequestException as e:
            msg = f"Download failed: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                msg += f"\nStatus: {e.response.status_code}\n{e.response.text}"
            raise RuntimeError(msg)

NODE_CLASS_MAPPINGS = {
    "NanogptTTSDownloader": NanogptTTSDownloader,
}

