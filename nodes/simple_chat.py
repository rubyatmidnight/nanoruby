"""
Simplified chat node with easy message handling.
Takes simple string inputs, handles JSON formatting internally.
"""
import json
import requests
from .utils import load_models, update_models_list as _update_models_list


def get_all_models():
    """Load all models from full list."""
    return load_models(favorites_first=True, fallback=["gpt-5", "deepseek-chat", "meta-llama/llama-3.3-70b-instruct"])


class SimpleChat:
    """
    Simplified chat node with string inputs.
    Handles message formatting internally.
    Outputs reply and updated history for chaining.
    """

    @classmethod
    def INPUT_TYPES(cls):
        models = get_all_models()
        return {
            "required": {
                "model": (models, {"default": models[0] if models else ""}),
                "user_message": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Your message to the AI"
                }),
                "api_key": ("STRING", {"default": "", "tooltip": "NanoGPT API key"}),
            },
            "optional": {
                "update_models_list": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Fetch latest models into nodes/models.json"
                }),
                "system_prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "System prompt (instructions for the AI)"
                }),
                "history": ("JSON", {
                    "default": [],
                    "tooltip": "Previous conversation history (connect from another chat node)"
                }),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 1024, "min": 1, "max": 8192}),
            }
        }

    RETURN_TYPES = ("STRING", "JSON", "JSON")
    RETURN_NAMES = ("reply", "history", "raw_response")
    FUNCTION = "chat"
    CATEGORY = "NanoGPT/Chat"

    def chat(self, model, user_message, api_key, update_models_list=False, system_prompt="", history=None,
             temperature=0.7, max_tokens=1024):
        update_info = None
        if update_models_list:
            try:
                update_info = _update_models_list(api_key=api_key, detailed=False)
            except Exception as e:
                update_info = {"error": str(e)}

        # Parse existing history or start fresh
        messages = []

        # Add system prompt if provided
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})

        # Parse history if provided (can be JSON string or list)
        if history:
            if isinstance(history, list):
                hist = history.copy()
                if system_prompt and system_prompt.strip():
                    hist = [m for m in hist if m.get("role") != "system"]
                messages.extend(hist)
            elif isinstance(history, str) and history.strip():
                try:
                    parsed = json.loads(history)
                    if isinstance(parsed, list):
                        if system_prompt and system_prompt.strip():
                            parsed = [m for m in parsed if m.get("role") != "system"]
                        messages.extend(parsed)
                except json.JSONDecodeError:
                    messages.append({"role": "assistant", "content": history.strip()})

        # Add the new user message
        if user_message.strip():
            messages.append({"role": "user", "content": user_message.strip()})

        # Make API call
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(
                "https://nano-gpt.com/api/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=120
            )
            resp.raise_for_status()
            result = resp.json()

            reply = result.get("reply") or result.get("choices", [{}])[0].get("text") or ""
            if update_info is not None:
                result = dict(result)
                result["models_update"] = update_info

            # Update history with the new exchange
            messages.append({"role": "assistant", "content": reply})

            # Return the updated history (without system prompt for cleaner chaining)
            history_out = [m for m in messages if m.get("role") != "system"]

            return (reply, history_out, result)

        except requests.exceptions.RequestException as e:
            error_msg = f"API Error: {str(e)}"
            meta = {"error": str(e)}
            if update_info is not None:
                meta["models_update"] = update_info
            return (error_msg, [], meta)


class MessageBuilder:
    """
    Build a messages array for chat nodes.
    Creates properly formatted JSON for chat APIs.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "user_message": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "system_prompt": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("messages",)
    FUNCTION = "build"
    CATEGORY = "NanoGPT/Chat"

    def build(self, user_message, system_prompt=""):
        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        if user_message.strip():
            messages.append({"role": "user", "content": user_message.strip()})
        return (messages,)


class MessageAppend:
    """
    Append a message to an existing conversation history.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "role": (["user", "assistant", "system"], {"default": "user"}),
                "content": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "history": ("JSON", {"default": []}),
            }
        }

    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("messages",)
    FUNCTION = "append"
    CATEGORY = "NanoGPT/Chat"

    def append(self, role, content, history=None):
        # Handle various input types
        if history is None:
            messages = []
        elif isinstance(history, list):
            messages = history.copy()
        elif isinstance(history, str):
            try:
                messages = json.loads(history)
                if not isinstance(messages, list):
                    messages = []
            except json.JSONDecodeError:
                messages = []
        else:
            messages = []

        if content.strip():
            messages.append({"role": role, "content": content.strip()})

        return (messages,)


# Node registration
NODE_CLASS_MAPPINGS = {
    "RubySimpleChat": SimpleChat,
    "RubyMessageBuilder": MessageBuilder,
    "RubyMessageAppend": MessageAppend,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RubySimpleChat": "Simple Chat (Midnight)",
    "RubyMessageBuilder": "Message Builder",
    "RubyMessageAppend": "Message Append",
}
