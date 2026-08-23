from __future__ import annotations

import json
import urllib.request


payload = {"message": "Give me three practical uses for a local LLM."}
body = json.dumps(payload).encode("utf-8")

request = urllib.request.Request(
    "http://127.0.0.1:8765/agents/default/chat",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(request, timeout=600) as response:
    data = json.loads(response.read().decode("utf-8"))

print(data["message"]["content"])

