import requests
import json

class NanogptTTSGenerator:
    """Generate text-to-speech using NanoGPT API."""
    
    def __init__(self):
        self.base_url = "https://nano-gpt.com/api"
        
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "Hello, this is a test of text-to-speech.",
                    "help": "Text to convert to natural-sounding speech."
                }),
                "model": (["Kokoro-82m", "Elevenlabs-Turbo-V2.5", "tts-1", "tts-1-hd", "gpt-4o-mini-tts"], {
                    "default": "Kokoro-82m",
                    "help": "TTS engine/model to use for synthesis."
                }),
                "api_key": ("STRING", {
                    "help": "API key for NanoGPT TTS generation."
                }),
            },
            "optional": {
                "voice": ("STRING", {
                    "default": "",
                    "help": "Voice style/type (leave blank for default)."
                }),
                "speed": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.25,
                    "max": 4.0,
                    "step": 0.1,
                    "help": "Readback speech rate. 1.0 = normal."
                }),
                "response_format": (["mp3", "wav", "opus", "flac"], {
                    "default": "mp3",
                    "help": "Audio file format for output."
                }),
                "instructions": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "help": "Instructions for speaking style (OpenAI/advanced engines only)."
                }),
                "stability": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "help": "Stability of voice (Elevenlabs only)."
                }),
                "similarity_boost": ("FLOAT", {
                    "default": 0.75,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "help": "Similarity to base voice (Elevenlabs)."
                }),
                "style": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "help": "Speech style expressivity (Elevenlabs)."
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING", "JSON")
    RETURN_NAMES = ("run_id", "status", "metadata")
    FUNCTION = "generate_tts"
    CATEGORY = "nanogpt/tts"
    
    def generate_tts(self, text, model, api_key, voice="", speed=1.0, response_format="mp3",
                     instructions="", stability=0.5, similarity_boost=0.75, style=0.0,
                     use_speech_endpoint=False):
        if not api_key:
            raise ValueError("API key is required.")
        payload = {"text": text, "model": model}
        if voice:
            payload["voice"] = voice
        if speed:
            payload["speed"] = speed
        if model.startswith(("tts-", "gpt-")):
            if response_format:
                payload["response_format"] = response_format
            if instructions:
                payload["instructions"] = instructions
        elif model == "Elevenlabs-Turbo-V2.5":
            if stability is not None:
                payload["stability"] = stability
            if similarity_boost is not None:
                payload["similarity_boost"] = similarity_boost
            if style is not None:
                payload["style"] = style
        endpoint = f"{self.base_url}/tts"
        if use_speech_endpoint:
            endpoint = f"{self.base_url}/v1/speech"
        try:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=120
            )
            response.raise_for_status()
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                result = response.json()
                run_id = result.get("runId", "")
                status = result.get("status", "completed" if "audioUrl" in result else "pending")
                audio_url = result.get("audioUrl", "")
                metadata = json.dumps({
                    "runId": run_id,
                    "status": status,
                    "model": model,
                    "audioUrl": audio_url
                })
                return (run_id, status, metadata)
            elif 'audio/' in content_type or 'application/octet-stream' in content_type:
                extension = content_type.split('/')[-1] if '/' in content_type else "mp3"
                filename = f"nanogpt_tts_{model}.{extension}"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                metadata = json.dumps({
                    "runId": "",
                    "status": "completed",
                    "model": model,
                    "audioFile": filename
                })
                return ("", "completed", metadata)
            else:
                raw_resp = response.text[:2000]
                err = f"Unexpected response format.\nStatus code: {response.status_code}\nContent-Type: {content_type}\nRaw response: {raw_resp}"
                if response.status_code == 401:
                    err += "\nLikely: Invalid API key."
                elif response.status_code == 400:
                    err += "\nLikely: Bad params (missing or invalid)."
                elif response.status_code == 429:
                    err += "\nLikely: Rate limit exceeded."
                elif "<html" in raw_resp or "<body" in raw_resp:
                    err += "\nGot HTML: Probably an error page."
                raise RuntimeError(err)
        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f"\nStatus: {e.response.status_code}\n{e.response.text}"
            raise RuntimeError(error_msg)


class NanogptSpeechTTSNode:
    """Generate speech instantly using NanoGPT /v1/speech endpoint."""
    RETURN_TYPES = ("STRING", "STRING", "JSON")
    RETURN_NAMES = ("audio_path", "status", "metadata")
    FUNCTION = "generate_speech"
    CATEGORY = "nanogpt/speech"

    @classmethod
    def INPUT_TYPES(cls):
        return NanogptTTSGenerator.INPUT_TYPES()

    def generate_speech(self, text, model, api_key, voice="", speed=1.0, response_format="mp3",
                        instructions="", stability=0.5, similarity_boost=0.75, style=0.0):
        generator = NanogptTTSGenerator()
        run_id, status, metadata = generator.generate_tts(
            text=text,
            model=model,
            api_key=api_key,
            voice=voice,
            speed=speed,
            response_format=response_format,
            instructions=instructions,
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speech_endpoint=True
        )
        metadata_json = json.loads(metadata)
        audio_path = metadata_json.get("audioFile", "")
        return (audio_path, status, metadata)

NODE_CLASS_MAPPINGS = {
    "NanogptTTSGenerator": NanogptTTSGenerator,
    "NanogptSpeechTTSNode": NanogptSpeechTTSNode,
}

