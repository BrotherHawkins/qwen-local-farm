# Platform Notes

This project is designed around a cross-platform Python operator script:

```bash
python sift.py setup
python sift.py start
python sift.py ask "Say hello."
python sift.py stop
```

The gateway itself uses only the Python standard library. Ollama is the main external dependency.

These notes call out platform-specific details so the root README can stay simple.

## Python Command

Different systems expose Python under different command names:

| Platform | Try first | Common fallback |
| --- | --- | --- |
| Windows | `python sift.py status` | `py -3 sift.py status` |
| macOS | `python3 sift.py status` | `python sift.py status` |
| Linux | `python3 sift.py status` | `python sift.py status` |

Python 3.10 or newer is recommended.

## Optional Tokenizer Setup

The default farm chunker uses character budgets and needs no extra Python packages.

Tokenizer-aware chunking is optional. It uses exact Hugging Face tokenizers for the supported Qwen/Ollama models, but it does not download model weights and does not require PyTorch.

Install the tokenizer dependencies:

```bash
python -m pip install --user "transformers>=5.15" "tokenizers>=0.22"
```

On macOS/Linux, use `python3 -m pip ...` if `python` is not available.

Cache and verify tokenizer assets:

```bash
python sift.py farm tokenizer setup
python sift.py farm tokenizer status
```

The cache and status reports live under:

```text
.run/tokenizers/
```

That folder is ignored by Git. After setup, `farm tokenizer status` verifies offline/local-only loading so normal token-aware runs do not need to fetch tokenizer files again.

Supported first-pass tokenizer mappings:

| Ollama model | Tokenizer ID |
| --- | --- |
| `qwen3.5:4b` | `Qwen/Qwen3.5-4B` |
| `qwen3:4b` | `Qwen/Qwen3-4B` |
| `qwen3:8b` | `Qwen/Qwen3-8B` |
| `qwen3:14b` | `Qwen/Qwen3-14B` |

If token-aware chunking reports a missing tokenizer, rerun `python sift.py farm tokenizer setup`. To avoid tokenizer setup entirely, use the default character strategy or pass `--chunk-strategy character`.

## Ollama Install

`python sift.py setup` checks for Ollama and prints platform-specific install help if it is missing.

After Ollama is installed, use [model installation guidance](model-installation.md) to choose the first local model/profile path for the machine. The machine-readable companion file is [model-installation.json](model-installation.json).

Common install paths:

| Platform | Option |
| --- | --- |
| Windows | `winget install --id Ollama.Ollama --source winget` |
| macOS | `brew install ollama` or download from `https://ollama.com/download/mac` |
| Linux | `curl -fsSL https://ollama.com/install.sh | sh` or use the package guidance at `https://ollama.com/download/linux` |

After installing Ollama, rerun:

```bash
python sift.py setup
```

On macOS/Linux, use `python3 sift.py setup` if `python` is not available.

## Startup And Shutdown

The cross-platform script stores process IDs and logs in `.run/`:

```text
.run/gateway.pid
.run/ollama.pid
.run/gateway.out.log
.run/gateway.err.log
.run/ollama.out.log
.run/ollama.err.log
```

`python sift.py start` starts Ollama if it is not already reachable, pulls the selected model if needed, and starts the gateway.

`python sift.py stop` stops the gateway process started by this project, unloads the selected model from Ollama, and stops the Ollama process if this project started it.

If Ollama was already running before this project started, `stop` may unload the selected model but leave the existing Ollama service alone.

## Shell-Specific Environment Variables

macOS/Linux shells:

```bash
SIFT_MODEL="qwen3:8b" python sift.py start
SIFT_GATEWAY_HOST="0.0.0.0" python sift.py start
```

PowerShell:

```powershell
$env:SIFT_MODEL = "qwen3:8b"
python sift.py start
```

Command Prompt:

```cmd
set SIFT_MODEL=qwen3:8b
python sift.py start
```

## Windows Notes

Windows users can use either:

```powershell
python sift.py start
```

or the convenience wrapper:

```powershell
.\sift.ps1 start
```

If PowerShell blocks script execution for `sift.ps1`, use:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

That changes execution policy only for the current PowerShell process.

For REST examples, Windows 10/11 usually includes `curl.exe`. In PowerShell, use `curl.exe` explicitly if `curl` resolves to a PowerShell alias.

## macOS Notes

This project has not been benchmarked on macOS in this PR. The expected path is:

```bash
python3 sift.py setup
python3 sift.py start
python3 sift.py ask "Say hello."
```

Apple Silicon machines use unified memory instead of separate NVIDIA-style VRAM. Ollama may use Metal acceleration when available. The `nvidia-smi` status output will not appear on macOS, which is expected.

If you installed Ollama as a GUI app and the `ollama` command is not on `PATH`, start the Ollama app once or add the CLI to your shell path. The Python script also checks common Homebrew and app-bundle locations.

## Linux Notes

This project has not been benchmarked on Linux in this PR. The expected path is:

```bash
python3 sift.py setup
python3 sift.py start
python3 sift.py ask "Say hello."
```

GPU support depends on the local driver stack. NVIDIA users should verify:

```bash
nvidia-smi
```

CPU/RAM-only agents such as `qwen8-cpu` and `qwen14-cpu` should still work without GPU support as long as the machine has enough system memory.

## LAN Access

The gateway binds to `127.0.0.1` by default. That keeps access limited to the local machine.

To expose it to other machines on a trusted private network:

```bash
SIFT_GATEWAY_HOST="0.0.0.0" python sift.py start
```

Then allow the gateway port, default `8765`, through the local OS firewall if needed.

Do not expose this service directly to the public internet.
