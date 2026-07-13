"""
Unified chat node for NanoGPT - consolidates all provider-specific chat nodes.
"""
import json
from .client import NanoGPTClient, build_chat_payload, extract_chat_result
from .utils import get_api_key, load_models, update_models_list as _update_models_list


# Provider configurations: tokens to filter by and fallback models
PROVIDERS = {
    "All Models": {
        "tokens": [],
        "fallback": ["gpt-5", "claude-sonnet-4-20250514", "deepseek-chat", "meta-llama/llama-3.3-70b-instruct"]
    },
    "Claude": {
        "tokens": ["claude"],
        "fallback": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]
    },
    "GPT": {
        "tokens": ["gpt-", "openai/gpt", "chatgpt-", "gpt-4", "gpt-5"],
        "fallback": ["openai/gpt-4.1", "gpt-5", "gpt-4-turbo"]
    },
    "Llama": {
        "tokens": ["llama", "nemotron"],
        "fallback": ["meta-llama/llama-3.3-70b-instruct", "llama-3-70b"]
    },
    "DeepSeek": {
        "tokens": ["deepseek"],
        "fallback": ["deepseek-chat", "deepseek-coder"]
    },
    "Gemini": {
        "tokens": ["gemini"],
        "fallback": ["gemini-2.0-flash", "gemini-pro", "gemini-1.5-pro"]
    },
    "Dolphin": {
        "tokens": ["dolphin"],
        "fallback": ["cognitivecomputations/dolphin-2.9.2-qwen2-72b", "dolphin-mixtral"]
    },
    "Venice": {
        "tokens": ["venice"],
        "fallback": ["venice-uncensored", "venice-uncensored:web"]
    },
    "Sonar": {
        "tokens": ["sonar"],
        "fallback": ["sonar-pro", "sonar-medium-online"]
    },
    "Uncensored": {
        "tokens": ["uncensored"],
        "fallback": ["venice-uncensored", "Gemma-3-27B-Nidum-Uncensored"]
    },
}


def get_models_for_provider(provider):
    """Get models filtered by provider configuration."""
    config = PROVIDERS.get(provider, PROVIDERS["All Models"])
    tokens = config["tokens"]
    fallback = config["fallback"]

    if tokens:
        return load_models(contains_any=tokens, favorites_first=True, fallback=fallback)
    else:
        return load_models(favorites_first=True, fallback=fallback)


def get_all_provider_models():
    """Get all models from all providers combined (for initial dropdown)."""
    return load_models(favorites_first=True, fallback=PROVIDERS["All Models"]["fallback"])


class NanoGPTChat:
    """
    Unified chat completion node for NanoGPT.
    Supports all model providers through a single interface.
    """

    @classmethod
    def INPUT_TYPES(cls):
        models = get_all_provider_models()
        return {
            "required": {
                "model": (models, {
                    "default": models[0] if models else "",
                    "tooltip": "Model to use for chat completion"
                }),
                "messages": ("JSON", {"tooltip": "Chat history/messages in OpenAI format"}),
                "api_key": ("STRING", {"tooltip": "NanoGPT API key"}),
            },
            "optional": {
                "update_models_list": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Fetch latest models into nodes/models.json"
                }),
                "system_prompt": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "System prompt for context"
                }),
                "temperature": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.05,
                    "tooltip": "Randomness (0=deterministic, 2=very random)"
                }),
                "top_p": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "tooltip": "Nucleus sampling threshold"
                }),
                "max_tokens": ("INT", {
                    "default": 1024,
                    "min": 1,
                    "max": 8192,
                    "tooltip": "Maximum tokens to generate"
                }),
                "reasoning_effort": (["auto", "none", "minimal", "low", "medium", "high", "xhigh"], {
                    "default": "auto",
                    "tooltip": "Reasoning effort when supported"
                }),
            }
        }

    RETURN_TYPES = ("STRING", "JSON")
    RETURN_NAMES = ("reply", "metadata")
    FUNCTION = "chat"
    CATEGORY = "NanoGPT/Chat"

    def chat(self, model, messages, api_key, update_models_list=False, system_prompt="",
             temperature=0.7, top_p=1.0, max_tokens=1024, reasoning_effort="auto"):
        api_key = get_api_key("master", api_key)
        if not api_key:
            raise ValueError("API key is required.")
        update_info = None
        if update_models_list:
            try:
                update_info = _update_models_list(api_key=api_key, detailed=True)
            except Exception as e:
                update_info = {"error": str(e)}

        payload = build_chat_payload(
            model,
            messages,
            system_prompt=system_prompt,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )
        result = NanoGPTClient(api_key).chat(payload)
        reply, reasoning, usage = extract_chat_result(result)
        metadata = dict(result)
        metadata["reasoning"] = reasoning
        metadata["usage"] = usage
        if update_info is not None:
            metadata["models_update"] = update_info
        return (reply, metadata)


# Node registration
# NOTE: Old provider-specific nodes (LlamaChat, GPTChat, etc.) are intentionally NOT registered.
# They were consolidated into NanoGPTChat. Do NOT add backward compatibility aliases.
# Users with old workflows will see ComfyUI's standard "missing node" error and can replace them.
NODE_CLASS_MAPPINGS = {
    "NanoGPTChat": NanoGPTChat,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NanoGPTChat": "NanoGPT Chat",
}
