from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RUN_DIR = ROOT / ".run"
GATEWAY_PID_FILE = RUN_DIR / "gateway.pid"
OLLAMA_PID_FILE = RUN_DIR / "ollama.pid"
GATEWAY_OUT_LOG = RUN_DIR / "gateway.out.log"
GATEWAY_ERR_LOG = RUN_DIR / "gateway.err.log"
OLLAMA_OUT_LOG = RUN_DIR / "ollama.out.log"
OLLAMA_ERR_LOG = RUN_DIR / "ollama.err.log"

DEFAULT_MODEL = "qwen3.5:4b"
MODEL = os.environ.get("QWEN_MODEL", DEFAULT_MODEL)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
GATEWAY_HOST = os.environ.get("QWEN_GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.environ.get("QWEN_GATEWAY_PORT", "8765"))
GATEWAY_BASE_URL = f"http://127.0.0.1:{GATEWAY_PORT}"


def ensure_run_dir() -> None:
    RUN_DIR.mkdir(exist_ok=True)


def ollama_host_value() -> str:
    parsed = urllib.parse.urlparse(OLLAMA_BASE_URL)
    if parsed.netloc:
        return parsed.netloc
    return "127.0.0.1:11434"


def find_ollama() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found

    candidates = []
    if platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        program_files = os.environ.get("ProgramFiles")
        program_files_x86 = os.environ.get("ProgramFiles(x86)")
        candidates.extend(
            [
                Path(local_app_data or "") / "Programs" / "Ollama" / "ollama.exe",
                Path(program_files or "") / "Ollama" / "ollama.exe",
                Path(program_files_x86 or "") / "Ollama" / "ollama.exe",
            ]
        )
    elif platform.system() == "Darwin":
        candidates.extend(
            [
                Path("/opt/homebrew/bin/ollama"),
                Path("/usr/local/bin/ollama"),
                Path("/Applications/Ollama.app/Contents/Resources/ollama"),
            ]
        )
    else:
        candidates.extend(
            [
                Path("/usr/local/bin/ollama"),
                Path("/usr/bin/ollama"),
            ]
        )

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)
    return None


def print_ollama_install_help() -> None:
    system = platform.system()
    print("Ollama was not found.")
    print("")
    if system == "Windows":
        print("Install option:")
        print("  winget install --id Ollama.Ollama --source winget")
        print("")
        print("Or download Ollama for Windows:")
        print("  https://ollama.com/download/windows")
    elif system == "Darwin":
        print("Install option if you use Homebrew:")
        print("  brew install ollama")
        print("")
        print("Or download Ollama for macOS:")
        print("  https://ollama.com/download/mac")
    else:
        print("Install option from Ollama:")
        print("  curl -fsSL https://ollama.com/install.sh | sh")
        print("")
        print("Or see:")
        print("  https://ollama.com/download/linux")
    print("")
    print("After installing Ollama, rerun:")
    print("  python qwen.py setup")
    print("")
    print("More platform notes are in docs/platforms.md.")


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 5) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def test_url(url: str) -> bool:
    try:
        request_json("GET", url, timeout=2)
        return True
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


def wait_url(url: str, name: str, seconds: int) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if test_url(url):
            return
        time.sleep(1)
    raise RuntimeError(f"{name} did not become ready at {url} within {seconds} seconds.")


def test_ollama_ready() -> bool:
    return test_url(f"{OLLAMA_BASE_URL}/api/tags")


def popen_kwargs(stdout_path: Path, stderr_path: Path) -> dict[str, Any]:
    ensure_run_dir()
    flags = 0
    if platform.system() == "Windows" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW
    return {
        "cwd": str(ROOT),
        "stdout": stdout_path.open("ab"),
        "stderr": stderr_path.open("ab"),
        "creationflags": flags,
    }


def start_ollama() -> None:
    ensure_run_dir()
    if test_ollama_ready():
        print(f"Ollama is already running at {OLLAMA_BASE_URL}")
        return

    ollama = find_ollama()
    if not ollama:
        print_ollama_install_help()
        raise SystemExit(1)

    env = os.environ.copy()
    env["OLLAMA_HOST"] = ollama_host_value()
    proc = subprocess.Popen(
        [ollama, "serve"],
        env=env,
        **popen_kwargs(OLLAMA_OUT_LOG, OLLAMA_ERR_LOG),
    )
    OLLAMA_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    wait_url(f"{OLLAMA_BASE_URL}/api/tags", "Ollama", 90)
    print(f"Ollama started at {OLLAMA_BASE_URL}")


def ensure_model(model_name: str | None = None) -> None:
    target_model = model_name or MODEL
    ollama = find_ollama()
    if not ollama:
        print_ollama_install_help()
        raise SystemExit(1)

    start_ollama()

    result = subprocess.run([ollama, "list"], check=True, text=True, capture_output=True)
    if target_model in result.stdout:
        print(f"Model is available: {target_model}")
        return

    print(f"Pulling {target_model}. This can take a while the first time.")
    subprocess.run([ollama, "pull", target_model], check=True)


def start_gateway() -> None:
    ensure_run_dir()
    if test_url(f"{GATEWAY_BASE_URL}/health"):
        print(f"Agent gateway is already running at {GATEWAY_BASE_URL}")
        return

    env = os.environ.copy()
    env["QWEN_MODEL"] = MODEL
    env["OLLAMA_BASE_URL"] = OLLAMA_BASE_URL
    env["QWEN_GATEWAY_HOST"] = GATEWAY_HOST
    env["QWEN_GATEWAY_PORT"] = str(GATEWAY_PORT)
    server = ROOT / "src" / "qwen_gateway.py"

    proc = subprocess.Popen(
        [sys.executable, str(server)],
        env=env,
        **popen_kwargs(GATEWAY_OUT_LOG, GATEWAY_ERR_LOG),
    )
    GATEWAY_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    wait_url(f"{GATEWAY_BASE_URL}/health", "Agent gateway", 30)
    print(f"Agent gateway started at {GATEWAY_BASE_URL}")


def stop_process_from_pid_file(pid_file: Path, name: str) -> None:
    if not pid_file.exists():
        print(f"{name} was not started by this script.")
        return

    raw = pid_file.read_text(encoding="utf-8").strip()
    if raw:
        pid = int(raw)
        try:
            if platform.system() == "Windows":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
            print(f"Stopped {name}.")
        except ProcessLookupError:
            print(f"{name} process was already stopped.")
        except PermissionError:
            print(f"Could not stop {name}; permission denied for PID {pid}.")

    pid_file.unlink(missing_ok=True)


def show_status() -> None:
    print(f"Model: {MODEL}")
    print(f"Ollama: {OLLAMA_BASE_URL}")
    print(f"Gateway: {GATEWAY_BASE_URL}")
    print(f"Platform: {platform.system()} {platform.release()}")

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        print("")
        print("GPU:")
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            check=False,
            text=True,
            capture_output=True,
        )
        if result.stdout.strip():
            print(result.stdout.strip())

    print("")
    if test_ollama_ready():
        print("Ollama status: running")
        try:
            tags = request_json("GET", f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            models = tags.get("models") or []
            if models:
                print("Installed models:")
                for item in models:
                    print(f"  {item.get('name')}")
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"Could not list Ollama models: {exc}")
    else:
        print("Ollama status: stopped or not installed")

    if test_url(f"{GATEWAY_BASE_URL}/health"):
        print("Gateway status: running")
    else:
        print("Gateway status: stopped")


def invoke_agent_prompt(message: str, agent: str) -> None:
    if not test_url(f"{GATEWAY_BASE_URL}/health"):
        print("Gateway is not running; starting local service first.")
        ensure_model()
        start_gateway()

    payload = {"message": message}
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{GATEWAY_BASE_URL}/agents/{agent}/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        data = json.loads(response.read().decode("utf-8"))
    print(data.get("message", {}).get("content", ""))


def print_logs() -> None:
    ensure_run_dir()
    for label, path in [
        ("Gateway stdout", GATEWAY_OUT_LOG),
        ("Gateway stderr", GATEWAY_ERR_LOG),
        ("Ollama stderr", OLLAMA_ERR_LOG),
    ]:
        print(f"{label}: {path}")
        if path.exists():
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-40:]:
                print(line)
        print("")


def stop_all() -> None:
    stop_process_from_pid_file(GATEWAY_PID_FILE, "agent gateway")
    ollama = find_ollama()
    if ollama and test_ollama_ready():
        result = subprocess.run([ollama, "stop", MODEL], check=False, text=True, capture_output=True)
        if result.returncode == 0:
            print(f"Unloaded model: {MODEL}")
        else:
            print(f"Model was not loaded: {MODEL}")
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip())
    stop_process_from_pid_file(OLLAMA_PID_FILE, "Ollama server")


def handle_farm(args: argparse.Namespace) -> None:
    from src import qwen_farm

    if args.farm_command == "run":
        agent, runtime_config = qwen_farm.resolve_run_agent_and_config(
            root=ROOT,
            agent_id=args.agent,
            default_model=MODEL,
            config_path=Path(args.config) if args.config else None,
            profile=args.profile,
            model=args.model,
            chunk_chars=args.chunk_chars,
            reduce_chars=args.reduce_chars,
            parallel_jobs=args.parallel_jobs,
            parallel_chunks=args.parallel_chunks,
        )
        ensure_model(str(agent["model"]))
        status = qwen_farm.run_farm(
            root=ROOT,
            input_folder=Path(args.input_folder),
            output_dir=Path(args.output) if args.output else None,
            mode=args.mode,
            instructions=args.instructions,
            agent_id=args.agent,
            default_model=MODEL,
            ollama_base_url=OLLAMA_BASE_URL,
            runtime_config=runtime_config,
        )
        print(f"Farm run complete: {status['run_id']}")
        print(f"Status: {status['status']}")
        print(f"Output: {status['output']['path']}")
        return

    if args.farm_command == "list":
        print(qwen_farm.list_runs_text(ROOT))
        return

    if args.farm_command == "status":
        print(qwen_farm.status_text(ROOT, args.run_id))
        return

    raise RuntimeError(f"Unknown farm command: {args.farm_command}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the local Qwen worker service.")
    subparsers = parser.add_subparsers(dest="command", required=False)

    for name in ["setup", "start", "stop", "status", "pull", "logs"]:
        subparsers.add_parser(name)

    ask = subparsers.add_parser("ask")
    ask.add_argument("message")
    ask.add_argument("agent", nargs="?", default="default")

    farm = subparsers.add_parser("farm")
    farm_subparsers = farm.add_subparsers(dest="farm_command", required=True)

    farm_run = farm_subparsers.add_parser("run")
    farm_run.add_argument("input_folder")
    farm_run.add_argument("--output")
    farm_run.add_argument("--mode", choices=["summarize", "prompt"], default="summarize")
    farm_run.add_argument("--instructions")
    farm_run.add_argument("--agent", default="default")
    farm_run.add_argument("--config")
    farm_run.add_argument("--profile")
    farm_run.add_argument("--model")
    farm_run.add_argument("--chunk-chars", type=int)
    farm_run.add_argument("--reduce-chars", type=int)
    farm_run.add_argument("--parallel-jobs", type=int)
    farm_run.add_argument("--parallel-chunks", type=int)

    farm_subparsers.add_parser("list")

    farm_status = farm_subparsers.add_parser("status")
    farm_status.add_argument("run_id", nargs="?")

    args = parser.parse_args()
    if not args.command:
        args.command = "status"
    return args


def main() -> None:
    args = parse_args()

    if args.command == "setup":
        if sys.version_info < (3, 10):
            raise RuntimeError("Python 3.10+ is required.")
        ensure_model()
        print("")
        print("Setup complete. Run `python qwen.py start` when you want the local service.")
    elif args.command == "start":
        ensure_model()
        start_gateway()
        print("")
        print("Ready.")
        print(f"OpenAI-compatible base URL: {OLLAMA_BASE_URL}/v1")
        print(f"Agent gateway: {GATEWAY_BASE_URL}")
    elif args.command == "stop":
        stop_all()
    elif args.command == "status":
        show_status()
    elif args.command == "ask":
        invoke_agent_prompt(args.message, args.agent)
    elif args.command == "pull":
        ensure_model()
    elif args.command == "logs":
        print_logs()
    elif args.command == "farm":
        handle_farm(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("")
        print("Interrupted.")
        raise SystemExit(130)
