# Model Installation Guidance

This guide helps a human or primary AI choose the first Sift model/profile path for a local machine.

Sift can inspect the machine and run a tiny local probe, but it should not silently install software, download models, write config, or change service environment variables. Treat this page as a conservative starting map, then verify with `farm doctor`, `farm recommend`, and a tiny smoke test.

Machine-readable guidance lives beside this page:

```text
docs/model-installation.json
schemas/model-installation.schema.json
```

## Quick Path

1. Check the local setup:

```bash
python sift.py farm doctor --json
```

2. Pick the closest hardware band below.

3. Ask before downloading the model:

```bash
ollama pull qwen3.5:4b
```

4. Run measured recommendations:

```bash
python sift.py farm recommend --agent default --profile local-8gb --resource-mode auto
```

5. Preview config before writing it:

```bash
python sift.py farm recommend apply
```

6. Only write config after review and approval:

```bash
python sift.py farm recommend apply --write
```

7. Run a tiny smoke folder before a large batch:

```bash
python sift.py farm run .run/smoke/input --mode summarize --output .run/smoke/output
```

## Hardware Bands

| Machine Shape | Start With | Why |
| --- | --- | --- |
| CPU-only or unknown GPU | `qwen8-cpu`, `cpu-small`, `cpu` | Slow, but avoids VRAM pressure. |
| Around 4 GB VRAM | `default`, `local-4gb`, `auto` | Conservative path for smaller GPUs. |
| Around 8 GB VRAM | `default`, `local-8gb`, `auto` | Sift's current comfortable default. |
| Around 12 GB VRAM | `qwen8`, `local-12gb`, `auto` | Worth measuring the deeper 8B worker. |
| Around 24 GB VRAM | `qwen8`, `local-24gb`, `auto` | 8B first; 14B only when depth matters. |
| Larger RAM/VRAM | `qwen14-hybrid`, `local-24gb`, `hybrid` | Stronger offline path, but measure locally. |
| Apple Silicon/unified memory | `default`, `local-8gb`, `auto` | Use doctor/recommend because VRAM bands do not map cleanly. |

## Recommended Model Pulls

These commands download model weights through Ollama. A primary AI should ask first.

| Model | Command | Use |
| --- | --- | --- |
| `qwen3.5:4b` | `ollama pull qwen3.5:4b` | Tested default and best first install for most users. |
| `qwen3:8b` | `ollama pull qwen3:8b` | Deeper offline worker after the default path is healthy. |
| `qwen3:14b` | `ollama pull qwen3:14b` | Slow, stronger offline worker for hybrid or CPU/RAM experiments. |

## Band Details

### CPU-Only Or Unknown GPU

Use this when the machine has no usable GPU, the GPU is unknown, or the user wants to avoid VRAM pressure.

```bash
ollama pull qwen3:8b
python sift.py farm doctor --json
python sift.py farm recommend --agent qwen8-cpu --profile cpu-small --resource-mode cpu
```

Smoke test:

```bash
python sift.py farm run .run/smoke/input --mode summarize --agent qwen8-cpu --profile cpu-small --resource-mode cpu --output .run/smoke/output
```

Expect this to be slower. Use it when stability and avoiding VRAM matter more than speed.

### Around 4 GB VRAM

Start with the tested default model and conservative profile.

```bash
ollama pull qwen3.5:4b
python sift.py farm doctor --json
python sift.py farm recommend --agent default --profile local-4gb --resource-mode auto
```

If this is unstable, retry with `--resource-mode cpu` or a CPU agent before raising chunk size or concurrency.

### Around 8 GB VRAM

This is Sift's original dogfood target.

```bash
ollama pull qwen3.5:4b
python sift.py farm doctor --json
python sift.py farm recommend --agent default --profile local-8gb --resource-mode auto
```

Start here unless the user has a clear reason to test a larger model.

### Around 12 GB VRAM

Use the default model first if the user wants reliability. Try `qwen8` when they want deeper local summaries.

```bash
ollama pull qwen3:8b
python sift.py farm doctor --json
python sift.py farm recommend --agent qwen8 --profile local-12gb --resource-mode auto
```

Do not raise parallelism until a single-job smoke test looks healthy.

### Around 24 GB VRAM

Start with 8B, then optionally test 14B.

```bash
ollama pull qwen3:8b
python sift.py farm recommend --agent qwen8 --profile local-24gb --resource-mode auto
```

Optional deeper trial:

```bash
ollama pull qwen3:14b
python sift.py farm recommend --agent qwen14-hybrid --profile local-24gb --resource-mode hybrid
```

The larger profile may allow more farm concurrency, but parallel load should still be measured before relying on it.

### Apple Silicon Or Unified Memory

Use the normal commands, but treat hardware fit as measure-first.

```bash
ollama pull qwen3.5:4b
python sift.py farm doctor --json
python sift.py farm recommend --agent default --profile local-8gb --resource-mode auto
```

NVIDIA-style VRAM output may not exist, and that is expected. Let the smoke test and timing records guide changes.

## Tokenizer Setup

Tokenizer-aware chunking is optional. It does not download model weights, but it may download tokenizer assets and may require Python packages. Ask before doing this setup.

```bash
python -m pip install --user "transformers>=5.15" "tokenizers>=0.22"
python sift.py farm tokenizer setup
python sift.py farm tokenizer status
```

Use token-aware chunking only after `farm tokenizer status` reports readiness for the selected model.

## What Reports Should Show

After this feature, `farm doctor --json` and `farm recommend --json` include a `model_installation_guidance` object with paths, selected band, selected model, missing model state, and approval-tagged next commands.

Use that object as a hint, not as permission to install. Downloads and config writes still need user approval.
