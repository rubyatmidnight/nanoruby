# ComfyUI NanoGPT Nodes

NanoGPT-only custom nodes for ComfyUI.

This repo now focuses on a small NanoGPT surface:

- chat
- text-to-speech
- image-to-video
- video status/download

Everything unrelated has been moved out to `comfyui-rubytools`.

## Install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/rubyatmidnight/comfyui-nanoruby
```

Restart ComfyUI after cloning or updating.

## Included Nodes

### Chat

- `NanoGPTChat`
- `RubySimpleChat`

Both use NanoGPT chat completions and can refresh `nodes/models.json` from inside the node.

### TTS

- `NanogptTTSGenerator`
- `NanogptSpeechTTSNode`
- `NanogptTTSStatus`
- `NanogptTTSDownloader`

### Video

- `NanogptImageToVideo`
- `NanogptVideoStatus`
- `NanogptVideoDownloader`

The video flow is intentionally narrower now:

- the generator is focused on image-to-video
- the default model list prefers image-to-video models
- the node accepts a ComfyUI image, public image URL, or image data URL
- status returns `run_id`, `model`, `status`, `video_url`, and `metadata`

## Models

Chat and video nodes can update `nodes/models.json` directly from the UI.

- enable `update_models_list`
- queue the node once
- reopen or refresh the node if the dropdown does not update immediately

## Tests

Focused unit tests live in `tests/`.

Run them with:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

## Notes

- old provider-specific chat nodes were intentionally removed
- this repo is not aiming for backward compatibility right now

## License

MIT