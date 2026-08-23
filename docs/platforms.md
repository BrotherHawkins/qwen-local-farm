# Platform Notes

This project is designed around a cross-platform Python operator script:

```bash
python qwen.py setup
python qwen.py start
python qwen.py ask "Say hello."
python qwen.py stop
```

The gateway itself uses only the Python standard library. Ollama is the main external dependency.

These notes call out platform-specific details so the root README can stay simple.

## Python Command

Different systems expose Python under different command names:

| Platform | Try first | Common fallback |
| --- | --- | --- |
| Windows | `python qwen.py status` | `py -3 qwen.py status` |
| macOS | `python3 qwen.py status` | `python qwen.py status` |
| Linux | `python3 qwen.py status` | `python qwen.py status` |

Python 3.10 or newer is recommended.

## Ollama Install

`python qwen.py setup` checks for Ollama and prints platform-specific install help if it is missing.

Common install paths:

| Platform | Option |
| --- | --- |
| Windows | `winget install --id Ollama.Ollama --source winget` |
| macOS | `brew install ollama` or download from `https://ollama.com/download/mac` |
| Linux | `curl -fsSL https://ollama.com/install.sh | sh` or use the package guidance at `https://ollama.com/download/linux` |

After installing Ollama, rerun:

```bash
python qwen.py setup
```

On macOS/Linux, use `python3 qwen.py setup` if `python` is not available.

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

`python qwen.py start` starts Ollama if it is not already reachable, pulls the selected model if needed, and starts the gateway.

`python qwen.py stop` stops the gateway process started by this project, unloads the selected model from Ollama, and stops the Ollama process if this project started it.

If Ollama was already running before this project started, `stop` may unload the selected model but leave the existing Ollama service alone.

## Shell-Specific Environment Variables

macOS/Linux shells:

```bash
QWEN_MODEL="qwen3:8b" python qwen.py start
QWEN_GATEWAY_HOST="0.0.0.0" python qwen.py start
```

PowerShell:

```powershell
$env:QWEN_MODEL = "qwen3:8b"
python qwen.py start
```

Command Prompt:

```cmd
set QWEN_MODEL=qwen3:8b
python qwen.py start
```

## Windows Notes

Windows users can use either:

```powershell
python qwen.py start
```

or the convenience wrapper:

```powershell
.\qwen.ps1 start
```

If PowerShell blocks script execution for `qwen.ps1`, use:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

That changes execution policy only for the current PowerShell process.

For REST examples, Windows 10/11 usually includes `curl.exe`. In PowerShell, use `curl.exe` explicitly if `curl` resolves to a PowerShell alias.

## macOS Notes

This project has not been benchmarked on macOS in this PR. The expected path is:

```bash
python3 qwen.py setup
python3 qwen.py start
python3 qwen.py ask "Say hello."
```

Apple Silicon machines use unified memory instead of separate NVIDIA-style VRAM. Ollama may use Metal acceleration when available. The `nvidia-smi` status output will not appear on macOS, which is expected.

If you installed Ollama as a GUI app and the `ollama` command is not on `PATH`, start the Ollama app once or add the CLI to your shell path. The Python script also checks common Homebrew and app-bundle locations.

## Linux Notes

This project has not been benchmarked on Linux in this PR. The expected path is:

```bash
python3 qwen.py setup
python3 qwen.py start
python3 qwen.py ask "Say hello."
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
QWEN_GATEWAY_HOST="0.0.0.0" python qwen.py start
```

Then allow the gateway port, default `8765`, through the local OS firewall if needed.

Do not expose this service directly to the public internet.
