"""Anthropic Messages API adapter.

Docs: https://docs.anthropic.com/claude/reference/messages_post

The request body uses the shape::

    {
      "model": "...",
      "system": "...",                # optional, str or list of blocks
      "messages": [
        {"role": "user" | "assistant",
         "content": str | [{"type": "text", "text": "..."}, ...]},
        ...
      ],
      ...
    }

The response body has::

    {
      "content": [{"type": "text", "text": "..."}, ...],
      ...
    }
"""

from __future__ import annotations

from typing import Any

from makkuro.protocol.base import CanonicalMessage, CanonicalRequest, ContentBlock


class AnthropicAdapter:
    name = "anthropic"
    upstream_path_prefixes = ("/v1/messages",)

    def decode_request(self, body: dict[str, Any]) -> CanonicalRequest:
        system = body.get("system")
        system_str: str | None
        if isinstance(system, str):
            system_str = system
        elif isinstance(system, list):
            parts: list[str] = []
            for block in system:
                if isinstance(block, dict) and block.get("type") == "text":
                    t = block.get("text")
                    if isinstance(t, str):
                        parts.append(t)
            system_str = "\n".join(parts) if parts else None
        else:
            system_str = None

        messages_in = body.get("messages") or []
        messages: list[CanonicalMessage] = []
        for m in messages_in:
            if not isinstance(m, dict):
                continue
            role = str(m.get("role", "user"))
            content = m.get("content")
            blocks: list[ContentBlock] = []
            if isinstance(content, str):
                blocks.append(ContentBlock(type="text", text=content))
            elif isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    btype = str(b.get("type", ""))
                    if btype == "text":
                        blocks.append(ContentBlock(type="text", text=str(b.get("text", ""))))
                    elif btype == "tool_use":
                        tool_input = b.get("input")
                        if not isinstance(tool_input, dict):
                            tool_input = {}
                        blocks.append(
                            ContentBlock(
                                type="tool_use",
                                tool_name=str(b.get("name", "")),
                                tool_input=tool_input,
                                extra={"id": b.get("id", "")},
                            )
                        )
                    elif btype == "tool_result":
                        blocks.append(
                            ContentBlock(
                                type="tool_result",
                                tool_output=b.get("content"),
                                extra={
                                    "tool_use_id": b.get("tool_use_id", ""),
                                    "is_error": b.get("is_error", False),
                                },
                            )
                        )
                    else:
                        blocks.append(ContentBlock(type=btype, extra=b))
            messages.append(CanonicalMessage(role=role, content_blocks=blocks))

        return CanonicalRequest(system=system_str, messages=messages, extra={})

    def encode_request(
        self, canonical: CanonicalRequest, original: dict[str, Any]
    ) -> dict[str, Any]:
        out = dict(original)
        if canonical.system is not None:
            # Preserve original system shape if possible.
            orig_sys = original.get("system")
            if isinstance(orig_sys, list):
                rebuilt: list[Any] = []
                remaining = canonical.system
                for block in orig_sys:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "text"
                        and isinstance(block.get("text"), str)
                    ):
                        # Naively assign the whole redacted system to the first
                        # text block; multi-block system messages are rare and
                        # will still pass through correctly since upstream
                        # joins them.
                        if remaining:
                            new_block = dict(block)
                            new_block["text"] = remaining
                            rebuilt.append(new_block)
                            remaining = ""
                        else:
                            # Drop empty text blocks to avoid API errors
                            # (cache_control on empty text is rejected).
                            pass
                    else:
                        rebuilt.append(block)
                out["system"] = rebuilt
            else:
                out["system"] = canonical.system
        elif "system" in out:
            out["system"] = None

        out_messages: list[dict[str, Any]] = []
        for m in canonical.messages:
            content_out: list[dict[str, Any]] = []
            for b in m.content_blocks:
                if b.type == "text":
                    content_out.append({"type": "text", "text": b.text or ""})
                elif b.type == "tool_use":
                    content_out.append(
                        {
                            "type": "tool_use",
                            "id": b.extra.get("id", ""),
                            "name": b.tool_name or "",
                            "input": b.tool_input or {},
                        }
                    )
                elif b.type == "tool_result":
                    content_out.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": b.extra.get("tool_use_id", ""),
                            "content": b.tool_output,
                            "is_error": b.extra.get("is_error", False),
                        }
                    )
                else:
                    content_out.append(dict(b.extra))
            out_messages.append({"role": m.role, "content": content_out})
        out["messages"] = out_messages
        return out

    def extract_response_text(
        self, body: dict[str, Any]
    ) -> list[tuple[list[str | int], str]]:
        out: list[tuple[list[str | int], str]] = []
        content = body.get("content")
        if not isinstance(content, list):
            return out
        for i, block in enumerate(content):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                out.append((["content", i, "text"], block["text"]))
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
