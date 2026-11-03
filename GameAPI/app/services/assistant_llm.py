"""One chat-completion call to the configured AI provider, with tools. Messages are kept in the OpenAI shape everywhere in our
code; this module converts them for Anthropic. Returns (text, tool_calls) where tool_calls = [{"id", "name", "args"}]."""
import json

import requests

from app.services import assistant_settings as cfg


class AssistantUnavailable(Exception):
    """The provider could not be reached or refused the request. The message is safe to log, never contains the key."""


def _openai_style(messages, tools, key, model, base_url):
    body = {"model": model, "messages": messages, "tools": [{"type": "function", "function": t} for t in tools], "tool_choice": "auto",
            "temperature": 0.2, "max_tokens": 400, "chat_template_kwargs": {"enable_thinking": False}}
    r = requests.post(f"{base_url}/chat/completions", json=body, timeout=30,
                      headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    if r.status_code != 200:
        raise AssistantUnavailable(f"provider answered HTTP {r.status_code}")
    msg = (r.json().get("choices") or [{}])[0].get("message") or {}
    calls = []
    for c in msg.get("tool_calls") or []:
        fn = c.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            args = {}
        calls.append({"id": c.get("id") or f"call_{len(calls)}", "name": fn.get("name"), "args": args if isinstance(args, dict) else {}})
    return (msg.get("content") or "").strip(), calls


def _anthropic_messages(messages):
    system, out = "", []
    for m in messages:
        if m["role"] == "system":
            system += m["content"] + "\n"
        elif m["role"] == "assistant" and m.get("tool_calls"):
            blocks = [{"type": "text", "text": m["content"]}] if m.get("content") else []
            for c in m["tool_calls"]:
                blocks.append({"type": "tool_use", "id": c["id"], "name": c["function"]["name"], "input": json.loads(c["function"]["arguments"] or "{}")})
            out.append({"role": "assistant", "content": blocks})
        elif m["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return system.strip(), out


def _anthropic_style(messages, tools, key, model, base_url):
    system, msgs = _anthropic_messages(messages)
    body = {"model": model, "max_tokens": 400, "temperature": 0.2, "system": system, "messages": msgs,
            "tools": [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]}
    r = requests.post(f"{base_url}/messages", json=body, timeout=30,
                      headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    if r.status_code != 200:
        raise AssistantUnavailable(f"provider answered HTTP {r.status_code}")
    text, calls = "", []
    for block in r.json().get("content") or []:
        if block.get("type") == "text":
            text += block.get("text", "")
        elif block.get("type") == "tool_use":
            calls.append({"id": block["id"], "name": block["name"], "args": block.get("input") or {}})
    return text.strip(), calls


def chat(messages, tools):
    p = cfg.provider()
    key = cfg.api_key(p)
    if not key:
        raise AssistantUnavailable("no API key saved")
    meta = cfg.PROVIDERS[p]
    try:
        fn = _anthropic_style if p == "anthropic" else _openai_style
        return fn(messages, tools, key, cfg.model(p), meta["base_url"])
    except requests.RequestException as e:
        raise AssistantUnavailable(f"could not reach the provider ({type(e).__name__})")
