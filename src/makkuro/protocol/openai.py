"""OpenAI Chat Completions adapter.

Docs: https://platform.openai.com/docs/api-reference/chat/create

Request body shape::

    {
      "model": "...",
      "messages": [
        {"role": "system|user|assistant|tool",
         "content": str | [{"type": "text", "text": "..."}, ...]},
        ...
      ],
      "tools": [...],
      ...
    }

Response body (non-streaming)::

    {
      "choices": [
        {"index": 0,
         "message": {"role": "assistant", "content": "..."},
         ...},
        ...
      ],
      ...
    }
"""

from __future__ import annotations

from typing import Any

from makkuro.protocol.base import CanonicalMessage, CanonicalRequest, ContentBlock


def _message_text_parts(content: Any) -> list[str]:
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        parts: list[str] = []
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") in ("text", "input_text") and isinstance(b.get("text"), str):
                parts.append(b["text"])
        return parts
    return []


class OpenAIAdapter:
    name = "openai"
    upstream_path_prefixes = ("/v1/chat/completions", "/v1/responses")

    def decode_request(self, body: dict[str, Any]) -> CanonicalRequest:
        messages_in = body.get("messages") or []
        system: str | None = None
        messages: list[CanonicalMessage] = []
        for m in messages_in:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role", "user"))
            texts = _message_text_parts(m.get("content"))
            if role == "system":
                # OpenAI's system message is structurally a regular message,
                # but we hoist the first one we see to ``canonical.system`` so
                # the redactor treats it consistently with the Anthropic path.
                if system is None and texts:
                    system = "\n".join(texts)
                    continue
            blocks = [ContentBlock(type="text", text=t) for t in texts]
            messages.append(CanonicalMessage(role=role, content_blocks=blocks))
        return CanonicalRequest(system=system, messages=messages, extra={})

    def encode_request(
        self, canonical: CanonicalRequest, original: dict[str, Any]
    ) -> dict[str, Any]:
        out = dict(original)
        orig_messages = original.get("messages") or []
        new_messages: list[dict[str, Any]] = []

        if canonical.system is not None:
            # Preserve the original system message's type (str vs list).
            first_system = next(
                (m for m in orig_messages if isinstance(m, dict) and m.get("role") == "system"),
                None,
            )
            if first_system is not None and isinstance(first_system.get("content"), list):
                new_messages.append(
                    {
                        "role": "system",
                        "content": [{"type": "text", "text": canonical.system}],
                    }
                )
            else:
                new_messages.append({"role": "system", "content": canonical.system})

        # Skip the first system in the original list so we don't duplicate it.
        saw_system = False
        cano_idx = 0
        for m in orig_messages:
            if not isinstance(m, dict):
                continue
            if m.get("role") == "system" and not saw_system:
                saw_system = True
                continue
            if cano_idx >= len(canonical.messages):
                new_messages.append(m)
                continue
            cm = canonical.messages[cano_idx]
            cano_idx += 1
            orig_content = m.get("content")
            new_texts = [b.text or "" for b in cm.content_blocks if b.type == "text"]
            if isinstance(orig_content, list):
                new_messages.append(
                    {
                        "role": cm.role,
                        "content": [{"type": "text", "text": t} for t in new_texts],
                    }
                )
            else:
                new_messages.append({"role": cm.role, "content": "\n".join(new_texts)})

        out["messages"] = new_messages
        return out

    def extract_response_text(
        self, body: dict[str, Any]
    ) -> list[tuple[list[str | int], str]]:
        out: list[tuple[list[str | int], str]] = []
        choices = body.get("choices")
        if not isinstance(choices, list):
            return out
        for i, choice in enumerate(choices):
            if not isinstance(choice, dict):
                continue
            msg = choice.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                out.append((["choices", i, "message", "content"], content))
            elif isinstance(content, list):
                for j, block in enumerate(content):
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        out.append(
                            (["choices", i, "message", "content", j, "text"], block["text"])
                        )
        return out

    def apply_response_text(
        self, body: dict[str, Any], edits: list[tuple[list[str | int], str]]
    ) -> dict[str, Any]:
        for path, new_text in edits:
            cursor: Any = body
            for step in path[:-1]:
                cursor = cursor[step]
            cursor[path[-1]] = new_text
        return body
