from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
DEFAULT_MODEL = os.environ.get("QWEN_MODEL", "qwen3.5:4b")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
HOST = os.environ.get("QWEN_GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("QWEN_GATEWAY_PORT", "8765"))


def read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data


def load_agents() -> dict[str, dict[str, Any]]:
    agents: dict[str, dict[str, Any]] = {}
    if not AGENTS_DIR.exists():
        return agents

    for path in sorted(AGENTS_DIR.glob("*.json")):
        agent = read_json_file(path)
        agent_id = str(agent.get("id") or path.stem)
        agent["id"] = agent_id
        agent.setdefault("name", agent_id)
        agent.setdefault("model", DEFAULT_MODEL)
        agent.setdefault("system_prompt", "")
        agent.setdefault("options", {})
        agents[agent_id] = agent
    return agents


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw)
        except json.JSONDecodeError:
            detail = {"error": raw}
        raise RuntimeError(json.dumps({"status": exc.code, "detail": detail})) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Ollama at {OLLAMA_BASE_URL}: {exc.reason}") from exc


def ollama_get(path: str) -> dict[str, Any]:
    return request_json("GET", f"{OLLAMA_BASE_URL}{path}")


def ollama_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return request_json("POST", f"{OLLAMA_BASE_URL}{path}", payload)


def public_agent(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": agent["id"],
        "name": agent.get("name", agent["id"]),
        "model": agent.get("model", DEFAULT_MODEL),
        "options": agent.get("options", {}),
    }


def messages_for_agent(agent: dict[str, Any], body: dict[str, Any]) -> list[dict[str, str]]:
    if "messages" in body:
        messages = body["messages"]
        if not isinstance(messages, list):
            raise ValueError("messages must be a list")
        normalized = []
        for item in messages:
            if not isinstance(item, dict):
                raise ValueError("each message must be an object")
            normalized.append(
                {
                    "role": str(item.get("role", "user")),
                    "content": str(item.get("content", "")),
                }
            )
    else:
        message = str(body.get("message", ""))
        if not message:
            raise ValueError("Provide either message or messages")
        normalized = [{"role": "user", "content": message}]

    system_prompt = str(agent.get("system_prompt", "")).strip()
    if system_prompt and not any(item["role"] == "system" for item in normalized):
        normalized.insert(0, {"role": "system", "content": system_prompt})

    return normalized


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "QwenGateway/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))
        sys.stdout.flush()

    def send_json(self, status: int, payload: dict[str, Any] | list[Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")
        return data

    def do_OPTIONS(self) -> None:
        self.send_json(204, {})

    def do_GET(self) -> None:
        try:
            path = urllib.parse.urlparse(self.path).path
            agents = load_agents()

            if path == "/health":
                try:
                    tags = ollama_get("/api/tags")
                    ollama_ok = True
                except RuntimeError as exc:
                    tags = {"error": str(exc)}
                    ollama_ok = False
                self.send_json(
                    200 if ollama_ok else 503,
                    {
                        "ok": ollama_ok,
                        "default_model": DEFAULT_MODEL,
                        "ollama_base_url": OLLAMA_BASE_URL,
                        "agents": sorted(agents),
                        "ollama": tags,
                    },
                )
                return

            if path == "/agents":
                self.send_json(200, {"agents": [public_agent(agent) for agent in agents.values()]})
                return

            if path == "/v1/models":
                self.send_json(200, ollama_get("/v1/models"))
                return

            self.send_json(404, {"error": "Not found"})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})

    def do_POST(self) -> None:
        try:
            path = urllib.parse.urlparse(self.path).path
            body = self.read_body()

            if path.startswith("/agents/") and path.endswith("/chat"):
                agent_id = path.split("/")[2]
                agents = load_agents()
                agent = agents.get(agent_id)
                if not agent:
                    self.send_json(404, {"error": f"Unknown agent: {agent_id}"})
                    return

                payload = {
                    "model": str(body.get("model") or agent.get("model") or DEFAULT_MODEL),
                    "messages": messages_for_agent(agent, body),
                    "stream": bool(body.get("stream", False)),
                    "options": {**agent.get("options", {}), **body.get("options", {})},
                }
                if "format" in body:
                    payload["format"] = body["format"]
                if "keep_alive" in body:
                    payload["keep_alive"] = body["keep_alive"]

                result = ollama_post("/api/chat", payload)
                self.send_json(
                    200,
                    {
                        "agent": public_agent(agent),
                        "model": payload["model"],
                        "message": result.get("message", {}),
                        "done": result.get("done", True),
                        "raw": result,
                    },
                )
                return

            if path == "/v1/chat/completions":
                body.setdefault("model", DEFAULT_MODEL)
                self.send_json(200, ollama_post("/v1/chat/completions", body))
                return

            self.send_json(404, {"error": "Not found"})
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON"})
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
        except RuntimeError as exc:
            self.send_json(502, {"error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"error": str(exc)})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), GatewayHandler)
    print(f"Qwen gateway listening on http://{HOST}:{PORT}", flush=True)
    print(f"Forwarding model calls to {OLLAMA_BASE_URL}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
